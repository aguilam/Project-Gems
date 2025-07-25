/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { Injectable } from '@nestjs/common';
import { PrismaService } from 'prisma/prisma.service';

export class User {
  telegramId: number;
  username?: string;
}

@Injectable()
export class UsersService {
  constructor(private prisma: PrismaService) {}

  async login(dto: User) {
    const user = await this.prisma.user.upsert({
      where: { telegramId: dto.telegramId },
      create: {
        telegramId: dto.telegramId,
        userName: dto.username ?? '',
        systemPrompt: '',
        premium: false,
        freeQuestions: 20,
        premiumQuestions: 0,
        defaultModel: { connect: { id: 2 } },
      },
      update: { userName: dto.username },
      include: { defaultModel: true },
    });
    return user;
  }

  async getUserByTelegramId(telegramId: number) {
    const user = await this.prisma.user.findUnique({
      where: { telegramId },
    });
    return user;
  }

  async updateUserInfo(dto: any) {
    const { telegramId, defaultModel, ...rest } = dto;
    if (!telegramId) throw new Error('telegramId is required');

    const data: any = { ...rest };

    if (defaultModel !== undefined) {
      const modelId = Number(defaultModel);
      if (Number.isNaN(modelId)) {
        throw new Error('defaultModel must be a number or numeric string');
      }
      data.defaultModel = {
        connect: { id: modelId },
      };
    }

    const user = await this.prisma.user.update({
      where: { telegramId },
      data,
      include: { defaultModel: true },
    });

    return user;
  }
}
