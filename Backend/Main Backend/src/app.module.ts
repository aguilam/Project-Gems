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
import { SentryModule } from '@sentry/nestjs/setup';
import { APP_FILTER } from '@nestjs/core';
import { SentryGlobalFilter } from '@sentry/nestjs/setup';
import { ConfigModule } from '@nestjs/config';

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
    SentryModule.forRoot(),
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: './.env',
    }),
  ],
  controllers: [AppController],
  providers: [
    AppService,
    sheduledEventsService,
    {
      provide: APP_FILTER,
      useClass: SentryGlobalFilter,
    },
  ],
})
export class AppModule {}
