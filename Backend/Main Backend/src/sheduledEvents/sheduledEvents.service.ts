import { Injectable } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { PrismaService } from 'prisma/prisma.service';
@Injectable()
export class sheduledEventsService {
  constructor(private prisma: PrismaService) {}

  @Cron(CronExpression.EVERY_DAY_AT_MIDNIGHT)
  async handleCron() {
    const users = await this.prisma.user.findMany({
      select: { id: true, premium: true },
    });
    for (const user of users) {
      try {
        await this.prisma.user.update({
          where: { id: user.id },
          data: {
            freeQuestions: user.premium ? 35 : 25,
            premiumQuestions: user.premium ? 4 : 0,
          },
        });
      } catch (err) {
        console.error(`Failed to add questions for user ${user.id}`, err);
      }
    }
  }
}
