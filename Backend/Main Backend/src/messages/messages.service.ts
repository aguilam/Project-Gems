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

export class MessageDTO {
  telegramId: number;
  prompt: string;
  image?: string;
  file?: FileDTO;
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

      let ocrResult = '';
      if (dto.image) {
        ocrResult = await this.ocrService.imageOcr(dto.image);
      }

      let fileRecognizeResult = '';
      if (dto.file) {
        fileRecognizeResult = await this.fileRecognizeService.recognize(
          dto.file,
        );
      }
      const chat = await this.chatsService.createChat(user?.id);

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
      if (ocrResult) {
        fullPrompt = `${ocrResult}\n\n${dto.prompt}`;
      } else if (fileRecognizeResult) {
        fullPrompt = `${fileRecognizeResult}\n\n${dto.prompt}`;
      } else {
        fullPrompt = dto.prompt;
      }

      const response = await axios.post('http://127.0.0.1:8000/llm', {
        prompt: fullPrompt,
        model: model.systemName,
        provider: model.provider,
        premium: user.premium,
        systemPrompt: user.systemPrompt,
      });

      const userMessage = await this.prisma.message.create({
        data: {
          chatId: chat.id,
          senderId: user.id,
          role: 'USER',
          content: fullPrompt,
        },
      });

      const responseData: { content: string; type: string } = response.data;

      await this.prisma.message.create({
        data: {
          chatId: chat.id,
          senderId: user.id,
          role: 'ASSISTANT',
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
