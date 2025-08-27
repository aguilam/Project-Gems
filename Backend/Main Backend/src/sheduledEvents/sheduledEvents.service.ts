import { Injectable } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { PrismaService } from 'prisma/prisma.service';
@Injectable()
export class sheduledEventsService {
  constructor(private prisma: PrismaService) {}

  @Cron(CronExpression.EVERY_DAY_AT_MIDNIGHT)
  async handleCron() {
    const users = await this.prisma.user.findMany({
      select: { id: true, subscription: true },
    });
    const subscriptions = await this.prisma.subscription.findMany();

    for (const subscription of subscriptions) {
      const date = new Date();
      try {
        if (subscription.validUntil < date) {
          await this.prisma.subscription.update({
            where: { id: subscription.id },
            data: {
              status: 'EXPIRED',
            },
          });
        }
      } catch (err) {
        console.error(`Failed to check time for  ${subscription.id}`, err);
      }
    }
    for (const user of users) {
      try {
        const userSubscriber = user.subscription.find(
          (sub) => sub.status == 'ACTIVE',
        );
        await this.prisma.user.update({
          where: { id: user.id },
          data: {
            freeQuestions: userSubscriber ? 35 : 20,
            premiumQuestions: userSubscriber ? 4 : 0,
          },
        });
      } catch (err) {
        console.error(`Failed to add questions for user ${user.id}`, err);
      }
    }
  }
}
