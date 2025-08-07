/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { BadRequestException, Injectable } from '@nestjs/common';
import { PrismaService } from 'prisma/prisma.service';

export class User {
  telegramId: number;
  username?: string;
}
export class UpdateUserDto {
  telegramId: number;
  userName?: string;
  systemPrompt?: string;
  defaultModelId?: string;
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
        freeQuestions: 25,
        premiumQuestions: 0,
        defaultModel: {
          connect: { id: '5f3ac64b-34a9-4edf-8805-b20b8b9d1596' },
        },
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

  async updateUserInfo(dto: UpdateUserDto) {
    const { telegramId, defaultModelId, ...rest } = dto;
    if (!telegramId) {
      throw new BadRequestException('telegramId is required');
    }

    const data: Record<string, unknown> = { ...rest };

    if (defaultModelId !== undefined) {
      data.defaultModelId = defaultModelId.trim();
    }

    const user = await this.prisma.user.update({
      where: { telegramId },
      data,
      include: { defaultModel: true },
    });
    return user;
  }
}
