/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { Injectable } from '@nestjs/common';
import { PrismaService } from 'prisma/prisma.service';

export interface Chat {
  id: number;
  title?: string;
}

@Injectable()
export class ChatsService {
  constructor(private prisma: PrismaService) {}

  async createChat(dto: any) {
    const chat = await this.prisma.chat.create({
      data: {
        title: 'Тестовый чат',
        type: false,
        users: {
          connect: [{ id: dto }],
        },
      },
    });
    return chat;
  }

  async getAllChats(telegramId: number) {
    const chats = await this.prisma.chat.findMany({
      where: { users: { some: { telegramId } } },
    });
    return chats;
  }

  async getChatById(chatId: number) {
    const chat = await this.prisma.chat.findUnique({
      where: { id: chatId },
    });

    return chat;
  }

  async deleteChat(id: number) {
    const chat = await this.prisma.chat.delete({
      where: { id },
    });
    return chat;
  }
}
