/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import {
  Injectable,
  ForbiddenException,
  HttpException,
  InternalServerErrorException,
  NotFoundException,
} from '@nestjs/common';
import axios from 'axios';
import { PrismaService } from 'prisma/prisma.service';
import { ChatsService } from 'src/chats/chats.service';
import { FileRecognizeService } from 'src/fileUpload/fileRecognize.service';
import { OcrService } from 'src/ocr/ocr.service';
import { ConfigService } from '@nestjs/config';
export interface FileDTO {
  buffer: string;
  name: string;
  mime: string;
}

export interface ResponseDTO {
  content: string;
  type: string;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
  };
}
export class MessageDTO {
  telegramId: string;
  prompt: string;
  image?: string;
  file?: FileDTO;
  isForwarded?: boolean;
  chatId?: string;
}
@Injectable()
export class MessagesService {
  constructor(
    private prisma: PrismaService,
    private chatsService: ChatsService,
    private ocrService: OcrService,
    private FileRecognizeService: FileRecognizeService,
    private configService: ConfigService,
  ) {}

  async sentUserMessage(dto: MessageDTO) {
    try {
      dto.telegramId = String(dto.telegramId);
      const user = await this.prisma.user.findUnique({
        where: {
          telegramId: dto.telegramId,
        },
        include: {
          subscription: true,
        },
      });

      if (!user) {
        throw new Error('Пользователь не найден');
      }
      let fullPrompt = dto.prompt;
      let ocrResult = '';
      let fileRecognizeResult = '';
      let modelId = user.defaultModelId;
      let questionsCost = 0;
      const previousMessages: { content: string; role: string }[] = [];
      if (dto.prompt.charAt(0) === '/') {
        const trimmedPrompt = dto.prompt.trim();

        const firstSpace = trimmedPrompt.indexOf(' ');

        const userCommand =
          firstSpace === -1
            ? trimmedPrompt
            : trimmedPrompt.slice(0, firstSpace);

        const rest =
          firstSpace === -1 ? '' : trimmedPrompt.slice(firstSpace + 1).trim();

        const shortcut = await this.prisma.shortcut.findFirst({
          where: {
            userId: user?.id,
            command: userCommand,
          },
        });

        if (shortcut) {
          fullPrompt = rest
            ? `${shortcut.instruction} ${rest}`
            : `${shortcut.instruction}`;
          modelId = shortcut.modelId;
        } else {
          fullPrompt = rest;
        }
      }
      const model = await this.prisma.aIModel.findUnique({
        where: {
          id: modelId,
        },
      });
      previousMessages.push({
        content: user.systemPrompt,
        role: 'system',
      });

      if (!model) {
        throw new Error('Модель не найдена');
      }

      if (model.premium && user.premiumQuestions <= 0) {
        throw new ForbiddenException(
          'У вас закончились премиум вопросы. Хотите получить больше? Попробуйте про подписку /pro',
        );
      }

      if (!model.premium && user.freeQuestions <= 0) {
        throw new ForbiddenException(
          'У вас закончились бесплатные вопросы. Хотите получить больше? Попробуйте про подписку /pro',
        );
      }

      if (dto.image) {
        ocrResult = await this.ocrService.imageOcr(dto.image);
        fullPrompt = `${ocrResult}\n\nЗапрос пользователя:${dto.prompt}`;
      }

      if (dto.file) {
        fileRecognizeResult = await this.FileRecognizeService.recognize(
          dto.file,
        );
        fullPrompt = `${fileRecognizeResult}\n\nЗапрос пользователя:${dto.prompt}`;
        if (fileRecognizeResult && model.premium !== true) {
          questionsCost++;
        }
      }

      let chat;
      if (dto.chatId && !(dto.chatId == '0')) {
        chat = await this.chatsService.getChatById(user.telegramId, dto.chatId);
        if (!chat || chat == null) {
          throw new NotFoundException(
            'Чат не найден, попробуйте выбрать другой',
          );
        }
        const chatMessages = chat.messages;
        for (let i = 0; i < chatMessages.length; i++) {
          previousMessages.push({
            content: chatMessages[i].content,
            role: chatMessages[i].role.toLowerCase(),
          });
        }
      } else {
        const response = await axios.post(
          `${this.configService.get<string>('LLM_SERVER_URL')}/llm`,
          {
            prompt: [
              {
                role: 'system',
                content: `You are a helpful assistant whose job is to generate concise, descriptive chat titles based on the user’s first message.
            
            Instructions:
            - Detect the language of the user’s message automatically.
            - Write the chat title in the same language.
            - Keep the title to a maximum of 5 words (ideally 3–4 words).
            - Capture the essence of the message; be clear and descriptive.
            - Provide only the title — nothing else, no explanation, no extra formatting.
            
            Examples:
            User says (English): "Can you help me plan a week-long trip to Japan with budget-friendly options?"
             Title: "Budget Japan Trip"
            
            User says (Russian): "Помоги составить план поездки на неделю в Японию с бюджетными опциями"
             Title: "Бюджетная поездка в Японию"
            
            User says (Spanish): "Necesito un resumen rápido de este artículo sobre cambio climático"
             Title: "Resumen Cambio Climático"
            
            Now, user says: "${fullPrompt}"`,
              },
            ],
            model: 'llama3.3-70b',
            provider: ['cerebras'],
            is_agent: false,
          },
          {
            headers: {
              'X-User-Id': 'system',
            },
          },
        );
        chat = await this.chatsService.createChat(
          user?.id,
          response.data.content as string,
        );
      }
      const userMessage = await this.prisma.message.create({
        data: {
          chatId: chat.id,
          senderId: user.id,
          role: 'user',
          content: fullPrompt,
        },
      });
      previousMessages.push({
        content: fullPrompt,
        role: 'user',
      });
      let response;
      try {
        const userSubscriber = user.subscription.find(
          (sub) => sub.status == 'ACTIVE' && sub.plan == 'PRO',
        );
        console.log(userSubscriber);
        response = await axios.post(
          `${this.configService.get<string>('LLM_SERVER_URL')}/llm`,
          {
            prompt: previousMessages,
            model: model.systemName,
            provider: model.provider,
            is_agent: userSubscriber ? true : false,
          },
          {
            headers: {
              'X-User-Id': String(user.id),
            },
            timeout: 60_000,
            maxContentLength: Infinity,
            maxBodyLength: Infinity,
          },
        );
      } catch (e) {
        console.error(
          'Ошибка при вызове LLM:',
          e?.response?.status,
          e?.response?.data ?? e.message ?? e,
        );
        throw new InternalServerErrorException(
          'Ошибка обращения с LLM: ' + String(e?.message ?? e),
        );
      }
      if (response) {
        questionsCost++;
        if (Number(response.headers['agent-use']) > 0) {
          questionsCost++;
        }
      }
      const responseData = response?.data as ResponseDTO | undefined;

      if (!responseData || typeof responseData.content !== 'string') {
        console.error('LLM returned invalid body', response?.data);
        throw new InternalServerErrorException('LLM вернул некорректный ответ');
      }

      const usage = {
        prompt_tokens: Number(responseData.usage?.prompt_tokens ?? 0),
        completion_tokens: Number(
          responseData.usage?.completion_tokens ??
            responseData.usage?.completion_tokens ??
            0,
        ),
      };

      try {
        if (responseData.type !== 'image') {
          await this.prisma.message.create({
            data: {
              chatId: chat.id,
              senderId: user.id,
              role: 'assistant',
              content: responseData.content,
              replyToId: userMessage.id,
            },
          });
        }
      } catch (e) {
        console.error('Prisma create message failed', e);
        throw new InternalServerErrorException('Ошибка сохранения сообщения');
      }

      try {
        await axios.post(
          'https://eu.i.posthog.com/i/v0/e/',
          {
            api_key: 'phc_7dIIXaRO6KyWSjenkV1cJ2xfvDjxgybB0cpLXxna78S',
            event: '$ai_generation',
            properties: {
              distinct_id: String(user.id),
              $ai_trace_id: chat.id,
              $ai_model: model.systemName,
              $ai_provider: 'openai',
              $ai_input_tokens: usage.prompt_tokens,
              $ai_output_tokens: usage.completion_tokens,
              $ai_input: [
                {
                  role: 'user',
                  content: [
                    {
                      type: 'text',
                      text: fullPrompt,
                    },
                  ],
                },
              ],
              $ai_output_choices: [
                {
                  role: 'assistant',
                  content: [
                    {
                      type: 'text',
                      text: responseData.content,
                    },
                  ],
                },
              ],
            },
            timestamp: new Date().toISOString(),
          },
          { headers: { 'Content-Type': 'application/json' }, timeout: 5000 },
        );
      } catch (e) {
        console.error(
          'PostHog ingestion failed, continuing without analytics:',
          e?.response?.status,
          e?.response?.data ?? e.message,
        );
      }
      if (model.premium) {
        await this.prisma.user.update({
          where: {
            telegramId: dto.telegramId,
          },
          data: {
            premiumQuestions: user.premiumQuestions - questionsCost,
          },
        });
      } else {
        await this.prisma.user.update({
          where: {
            telegramId: dto.telegramId,
          },
          data: {
            freeQuestions: user.freeQuestions - questionsCost,
          },
        });
      }

      return {
        content: responseData.content,
        type: responseData.type,
        chatId: chat.id,
      };
    } catch (error) {
      if (error instanceof HttpException) {
        throw error;
      }

      throw new InternalServerErrorException(
        'Внутренняя ошибка сервера, попробуйте позже',
      );
    }
  }
}
