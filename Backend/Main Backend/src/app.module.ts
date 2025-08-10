import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { PrismaModule } from 'prisma/prisma.module';
import { UsersModule } from './users/users.module';
import { MessagesModule } from './messages/messages.module';
import { ChatsModule } from './chats/chats.module';
import { ModelsModule } from './models/models.module';
import { ScheduleModule } from '@nestjs/schedule';
import { sheduledEventsService } from './sheduledEvents/sheduledEvents.service';
import { SubscriptionsModule } from './subscriptions/subscriptions.module';
import { ShortcutsModule } from './shortcuts/shortcuts.module';
@Module({
  imports: [
    PrismaModule,
    UsersModule,
    MessagesModule,
    ChatsModule,
    ModelsModule,
    SubscriptionsModule,
    ShortcutsModule,
    ScheduleModule.forRoot(),
  ],
  controllers: [AppController],
  providers: [AppService, sheduledEventsService],
})
export class AppModule {}
