import { Injectable } from '@nestjs/common';
import { PrismaService } from 'prisma/prisma.service';

@Injectable()
export class SubscriptionsService {
  constructor(private prisma: PrismaService) {}

  async newSubscription(dto: {
    userId: string;
    telegramPaymentId: string;
    providerPaymentId: string;
  }) {
    const validUntil = new Date();
    validUntil.setMonth(validUntil.getMonth() + 1);
    await this.prisma.subscription.upsert({
      where: { userId: dto.userId },
      create: {
        userId: dto.userId,
        status: 'ACTIVE',
        validUntil: validUntil,
        telegramPaymentId: dto.telegramPaymentId,
        providerPaymentId: dto.providerPaymentId,
      },
      update: {
        status: 'ACTIVE',
      },
    });

    return true;
  }
}
