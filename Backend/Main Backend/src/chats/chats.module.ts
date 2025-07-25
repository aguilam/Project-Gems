import { Module } from '@nestjs/common';
import { ChatsController } from './chats.controller';
import { ChatsService } from './chats.service';

@Module({
  exports: [ChatsService],
  controllers: [ChatsController],
  providers: [ChatsService],
})
export class ChatsModule {}
