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
      });

      if (!user) {
        throw new Error('Пользователь не найден');
      }

      const model = await this.prisma.aIModel.findUnique({
        where: {
          id: user.defaultModelId,
        },
      });

      if (!model) {
        throw new Error('Модель не найдена');
      }

      if (model.premium && (!user.premium || user.premiumQuestions <= 0)) {
        throw new ForbiddenException('Пользователь не обладает premium');
      }

      if (!model.premium && user.freeQuestions <= 0) {
        throw new ForbiddenException(
          'У пользователя закончились бесплатные вопросы',
        );
      }

      let fullPrompt = '';
      let ocrResult = '';
      let fileRecognizeResult = '';

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
      } else {
        fullPrompt = dto.prompt;
      }
      let chat;
      const previousMessages: { content: string; role: string }[] = [
        {
          content: user.systemPrompt,
          role: 'system',
        },
      ];
      if (dto.chatId) {
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
        chat = await this.chatsService.createChat(user?.id);
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
      const response = await axios.post('http://127.0.0.1:8000/llm', {
        prompt: previousMessages,
        model: model.systemName,
        provider: model.provider,
        premium: user.premium,
        is_agent: false,
      });
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
