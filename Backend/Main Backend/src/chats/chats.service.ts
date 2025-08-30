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

  async createChat(userId: string, title: string) {
    const chat = await this.prisma.chat.create({
      data: {
        title: title,
        type: false,
        users: {
          connect: [{ id: userId }],
        },
      },
    });
    return chat;
  }

  async getAllChats(telegramId: string, page: number) {
    const take = 10;
    const chats = await this.prisma.chat.findMany({
      where: { users: { some: { telegramId } } },
      skip: (page - 1) * take,
      take: take,
      orderBy: { updatedAt: 'desc' },
    });
    const countUserChats = await this.prisma.chat.count({
      where: { users: { some: { telegramId } } },
    });
    const pagesCount = Math.ceil(countUserChats / take);
    return { chats: chats, pagesCount: pagesCount };
  }

  async getChatById(
    telegramId: string,
    chatId: string,
  ): Promise<ChatWithMessages | null> {
    const chat = await this.prisma.chat.findUnique({
      where: { id: chatId, users: { some: { telegramId: telegramId } } },
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
    await this.prisma.message.deleteMany({
      where: { chatId: id },
    });
    return await this.prisma.chat.delete({
      where: { id },
    });
  }

  async editChat(chatDTO: { id: string; title: string }) {
    const { id, title } = chatDTO;
    const chat = await this.prisma.chat.update({
      where: { id },
      data: { title: title },
    });
    return chat;
  }
}
