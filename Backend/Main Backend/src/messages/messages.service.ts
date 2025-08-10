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
import { fileRecognizeService } from 'src/fileUpload/fileRecognize.service';
import { OcrService } from 'src/ocr/ocr.service';

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
  telegramId: number;
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
    private fileRecognizeService: fileRecognizeService,
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
      previousMessages.push({
        content: user.systemPrompt,
        role: 'system',
      });
      const model = await this.prisma.aIModel.findUnique({
        where: {
          id: modelId,
        },
      });

      if (!model) {
        throw new Error('Модель не найдена');
      }

      if (
        model.premium &&
        (!(user.subscription?.status == 'ACTIVE') || user.premiumQuestions <= 0)
      ) {
        throw new ForbiddenException('Пользователь не обладает premium');
      }

      if (!model.premium && user.freeQuestions <= 0) {
        throw new ForbiddenException(
          'У пользователя закончились бесплатные вопросы',
        );
      }

      if (dto.image) {
        ocrResult = await this.ocrService.imageOcr(dto.image);
      }

      if (dto.file) {
        fileRecognizeResult = await this.fileRecognizeService.recognize(
          dto.file,
        );
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
          'http://127.0.0.1:8000/llm',
          {
            prompt: [
              {
                role: 'user',
                content: `Придумай название чата в пяти словах на основе этого сообщения, используй только слова, без смайликов, и символов типа "'/:}[] - "${dto.prompt}"`,
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
      if (!(fileRecognizeResult.trim() == '') && dto.isForwarded == true) {
        return {
          content: fileRecognizeResult,
          type: 'text',
        };
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
      const response = await axios.post(
        'http://127.0.0.1:8000/llm',
        {
          prompt: previousMessages,
          model: model.systemName,
          provider: model.provider,
          premium: true,
          is_agent: true,
        },
        {
          headers: {
            'X-User-Id': user.id,
          },
        },
      );
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
            premiumQuestions: user.premiumQuestions - 1,
          },
        });
      } else {
        await this.prisma.user.update({
          where: {
            telegramId: dto.telegramId,
          },
          data: {
            freeQuestions: user.freeQuestions - 1,
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
