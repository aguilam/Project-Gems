import { Body, Controller, Post } from '@nestjs/common';
import { SubscriptionsService } from './subscriptions.service';
import { SubscriptionPlan } from '@prisma/client';

@Controller('subscriptions')
export class SubscriptionsController {
  constructor(private subscriptionsService: SubscriptionsService) {}

  @Post()
  newSubscription(
    @Body()
    dto: {
      userId: string;
      plan: SubscriptionPlan;
      telegramPaymentId: string;
      providerPaymentId: string;
    },
  ) {
    return this.subscriptionsService.newSubscription(dto);
  }

  @Post('trial')
  newTrialSubscription(@Body() dto: { userId: string }) {
    return this.subscriptionsService.newTrialSubscription(dto);
  }
}
