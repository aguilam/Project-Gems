/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { Injectable } from '@nestjs/common';
import axios from 'axios';
import { PrismaService } from 'prisma/prisma.service';
import { ChatsService } from 'src/chats/chats.service';

export class MessageDTO {
  telegramId: number;
  prompt: string;
}

@Injectable()
export class MessagesService {
  constructor(
    private prisma: PrismaService,
    private chatsService: ChatsService,
  ) {}

  async sentUserMessage(dto: MessageDTO) {
    try {
      const user = await this.prisma.user.findUnique({
        where: {
          telegramId: dto.telegramId,
        },
      });
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
        throw new Error('Пользователь не найден');
      }

      const response = await axios.post('http://127.0.0.1:8000/llm', {
        prompt: dto.prompt,
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
          content: dto.prompt,
        },
      });

      await this.prisma.message.create({
        data: {
          chatId: chat.id,
          senderId: user.id,
          role: 'ASSISTANT',
          content: model.tags.includes('image')
            ? Buffer.from(response.data).toString('base64')
            : response.data,
          replyToId: userMessage.id,
        },
      });

      console.log(response);
      return {
        content: response.data,
        type: model.tags.includes('image') ? 'image' : 'text',
      };
    } catch (error) {
      throw new Error(error);
    }
  }
}
