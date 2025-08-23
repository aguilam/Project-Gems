/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import {
  Injectable,
  ForbiddenException,
  HttpException,
  InternalServerErrorException,
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
      if (dto.prompt.charAt(0) == '/') {
        const trimmedPrompt = dto.prompt.trim();
        const endCommandPosition = dto.prompt.indexOf(' ');
        const userCommand = trimmedPrompt.slice(0, endCommandPosition);
        fullPrompt = trimmedPrompt.slice(
          endCommandPosition,
          trimmedPrompt.length,
        );
        const shortcut = await this.prisma.shortcut.findFirst({
          where: {
            userId: user?.id,
            command: userCommand,
          },
        });
        if (shortcut) {
          fullPrompt = `${shortcut.instruction} ${fullPrompt}`;
          modelId = shortcut?.modelId;
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

      if (
        model.premium &&
        (!(user.subscription?.status == 'ACTIVE') || user.premiumQuestions <= 0)
      ) {
        throw new ForbiddenException('У вас закончились премиум вопросы');
      }

      if (!model.premium && user.freeQuestions <= 0) {
        throw new ForbiddenException('У вас закончились бесплатные вопросы');
      }

      if (dto.image) {
        ocrResult = await this.ocrService.imageOcr(dto.image);
      }

      if (dto.file) {
        fileRecognizeResult = await this.FileRecognizeService.recognize(
          dto.file,
        );

        if (fileRecognizeResult && model.premium !== true) {
          questionsCost++;
        }
      }

      if (ocrResult) {
        fullPrompt = `${ocrResult}\n\n${dto.prompt}`;
      } else if (!(fileRecognizeResult.trim() == '')) {
        fullPrompt = `${fileRecognizeResult}\n\n${dto.prompt}`;
      }
      let chat;
      if (dto.chatId && !(dto.chatId == '0')) {
        chat = await this.chatsService.getChatById(dto.chatId);
        if (!chat) {
          throw new Error('Чат не найден');
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
            premium: true,
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
      //if (!(fileRecognizeResult.trim() == '') && dto.isForwarded == true) {
      //  return {
      //    content: fileRecognizeResult,
      //    type: 'text',
      //  };
      //}
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
      const response = await axios.post(
        `${this.configService.get<string>('LLM_SERVER_URL')}/llm`,
        {
          prompt: previousMessages,
          model: model.systemName,
          provider: model.provider,
          premium: true,
          is_agent: user.subscription?.status == 'ACTIVE',
        },
        {
          headers: {
            'X-User-Id': user.id,
          },
        },
      );
      if (response) {
        questionsCost++;
        if (Number(response.headers['agent-use']) > 0) {
          questionsCost++;
        }
      }
      const responseData: ResponseDTO = response.data;
      await this.prisma.message.create({
        data: {
          chatId: chat.id,
          senderId: user.id,
          role: 'assistant',
          content: responseData.content,
          replyToId: userMessage.id,
        },
      });

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
