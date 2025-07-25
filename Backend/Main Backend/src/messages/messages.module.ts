import { Module } from '@nestjs/common';
import { MessagesController } from './messages.controller';
import { MessagesService } from './messages.service';
import { ChatsModule } from 'src/chats/chats.module';

@Module({
  imports: [ChatsModule],
  controllers: [MessagesController],
  providers: [MessagesService],
})
export class MessagesModule {}
