/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { BadRequestException, Injectable } from '@nestjs/common';
import { PrismaService } from 'prisma/prisma.service';

export class User {
  telegramId: string;
  username?: string;
}
export class UpdateUserDto {
  telegramId: string;
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

  async getUserByTelegramId(telegramId: string) {
    const user = await this.prisma.user.findUnique({
      where: { telegramId },
      include: {
        subscription: true,
        defaultModel: true,
      },
    });
    return user;
  }

  async updateUserInfo(dto: UpdateUserDto) {
    const { telegramId, defaultModelId, ...rest } = dto;
    if (!telegramId) {
      throw new BadRequestException('telegramId is required');
    }

    const updateData: Record<string, any> = { ...rest };

    if (defaultModelId !== undefined) {
      const trimmedId = defaultModelId.trim();

      const model = await this.prisma.aIModel.findUnique({
        where: { id: trimmedId },
      });
      if (!model) {
        throw new BadRequestException(`Модель с id="${trimmedId}" не найдена.`);
      }

      updateData.defaultModel = { connect: { id: trimmedId } };
    }

    const user = await this.prisma.user.update({
      where: { telegramId },
      data: updateData,
      include: { defaultModel: true },
    });
    return user;
  }
}
