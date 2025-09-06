import { Injectable } from '@nestjs/common';
import { PrismaService } from 'prisma/prisma.service';
import { PostHog } from 'posthog-node';
import { SubscriptionPlan } from '@prisma/client';
import { ConfigService } from '@nestjs/config';
@Injectable()
export class SubscriptionsService {
  constructor(
    private prisma: PrismaService,
    private configService: ConfigService,
  ) {}

  async newSubscription(dto: {
    userId: string;
    plan: SubscriptionPlan;
    telegramPaymentId: string;
    providerPaymentId: string;
  }) {
    const client = new PostHog(this.configService.get<string>('POSTHOG_KEY')!, {
      host: 'https://eu.i.posthog.com',
    });
    const validUntil = new Date();
    validUntil.setMonth(validUntil.getMonth() + 1);
    await this.prisma.subscription.create({
      data: {
        userId: dto.userId,
        status: 'ACTIVE',
        validUntil: validUntil,
        telegramPaymentId: dto.telegramPaymentId,
        providerPaymentId: dto.providerPaymentId,
        kind: 'PAID',
        plan: dto.plan,
      },
    });
    if (dto.plan == 'PRO') {
      client.capture({
        distinctId: dto.userId,
        event: 'Purchase Succeeded',
        properties: {
          value: 500,
          currency: 'RUB',
        },
      });
    } else if (dto.plan == 'GO') {
      client.capture({
        distinctId: dto.userId,
        event: 'Purchase Succeeded',
        properties: {
          value: 350,
          currency: 'RUB',
        },
      });
    }

    await client.shutdown();

    await this.prisma.user.update({
      where: {
        id: dto.userId,
      },
      data: {
        freeQuestions: 35,
        premiumQuestions: 4,
      },
    });

    return true;
  }

  async newTrialSubscription(dto: { userId: string }) {
    const existingSubscription = await this.prisma.subscription.findFirst({
      where: { userId: dto.userId },
    });
    if (!existingSubscription) {
      const client = new PostHog(
        'phc_7dIIXaRO6KyWSjenkV1cJ2xfvDjxgybB0cpLXxna78S',
        { host: 'https://eu.i.posthog.com' },
      );
      const validUntil = new Date();
      validUntil.setDate(validUntil.getDate() + 14);
      await this.prisma.subscription.create({
        data: {
          userId: dto.userId,
          status: 'ACTIVE',
          validUntil: validUntil,
          kind: 'TRIAL',
          plan: 'PRO',
        },
      });

      client.capture({
        distinctId: dto.userId,
        event: 'Trial started',
      });

      await client.shutdown();

      await this.prisma.user.update({
        where: {
          id: dto.userId,
        },
        data: {
          freeQuestions: 35,
          premiumQuestions: 4,
        },
      });
      return true;
    } else {
      throw new Error(
        'Активировать пробный период не удалось. У вас уже была активирована подписка',
      );
    }
  }
}
