import { Body, Controller, Post } from '@nestjs/common';
import { PrismaService } from 'prisma/prisma.service';
import { SubscriptionsService } from './subscriptions.service';

@Controller('subscriptions')
export class SubscriptionsController {
  constructor(
    private prismaService: PrismaService,
    private subscriptionsService: SubscriptionsService,
  ) {}

  @Post()
  newSubscription(
    @Body()
    dto: {
      userId: string;
      telegramPaymentId: string;
      providerPaymentId: string;
    },
  ) {
    return this.subscriptionsService.newSubscription(dto);
  }
}
