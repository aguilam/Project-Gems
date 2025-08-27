/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { BadRequestException, Injectable } from '@nestjs/common';
import { PrismaService } from 'prisma/prisma.service';
import { PostHog } from 'posthog-node';
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
    const client = new PostHog(
      'phc_7dIIXaRO6KyWSjenkV1cJ2xfvDjxgybB0cpLXxna78S',
      { host: 'https://eu.i.posthog.com' },
    );

    dto.telegramId = String(dto.telegramId);
    const existing_user = await this.prisma.user.findUnique({
      where: { telegramId: dto.telegramId },
    });
    const is_existing_user = existing_user == null ? false : true;
    const user = await this.prisma.user.upsert({
      where: { telegramId: dto.telegramId },
      create: {
        telegramId: dto.telegramId,
        userName: dto.username ?? '',
        systemPrompt: '',
        freeQuestions: 20,
        premiumQuestions: 0,
        defaultModel: {
          connect: { id: '5f3ac64b-34a9-4edf-8805-b20b8b9d1596' },
        },
      },
      update: { userName: dto.username },
      include: { defaultModel: true },
    });

    if (!is_existing_user) {
      client.capture({
        distinctId: user.id,
        event: 'New User',
      });
    }
    return { user: user, existing: is_existing_user };
  }

  async getUserByTelegramId(telegramId: string) {
    telegramId = String(telegramId);
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
    const { defaultModelId, telegramId: incomingTelegramId, ...rest } = dto;
    const telegramId = String(incomingTelegramId);
    if (!telegramId) throw new BadRequestException('telegramId is required');

    const updateData: Record<string, any> = { ...rest };

    if (defaultModelId !== undefined) {
      const trimmedId = defaultModelId.trim();
      const model = await this.prisma.aIModel.findUnique({
        where: { id: trimmedId },
      });
      if (!model)
        throw new BadRequestException(`Модель с id="${trimmedId}" не найдена.`);
      updateData.defaultModel = { connect: { id: trimmedId } };
    }

    if ('telegramId' in updateData) delete updateData.telegramId;

    const user = await this.prisma.user.update({
      where: { telegramId },
      data: updateData,
      include: { defaultModel: true },
    });
    return user;
  }
}
