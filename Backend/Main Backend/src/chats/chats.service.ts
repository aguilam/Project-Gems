/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { Injectable } from '@nestjs/common';
import { PrismaService } from 'prisma/prisma.service';
import { Prisma } from '@prisma/client';

export interface Chat {
  id: number;
  createdAt: Date;
  title: string;
  type: boolean;
  updatedAt: Date;
}
type ChatWithMessages = Prisma.ChatGetPayload<{
  include: {
    messages: {
      select: {
        senderId: true;
        content: true;
        role: true;
      };
    };
  };
}>;
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

  async getChatById(chatId: string): Promise<ChatWithMessages | null> {
    const chat = await this.prisma.chat.findUnique({
      where: { id: chatId },
      include: {
        messages: {
          select: {
            senderId: true,
            content: true,
            role: true,
          },
        },
      },
    });

    return chat;
  }

  async deleteChat(id: string) {
    const chat = await this.prisma.chat.delete({
      where: { id },
    });
    return chat;
  }
}
