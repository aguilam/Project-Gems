import { Body, Controller, Post } from '@nestjs/common';
import { SubscriptionsService } from './subscriptions.service';

@Controller('subscriptions')
export class SubscriptionsController {
  constructor(private subscriptionsService: SubscriptionsService) {}

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
