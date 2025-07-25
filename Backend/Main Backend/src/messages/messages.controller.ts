import { Body, Controller, Post } from '@nestjs/common';
import { MessagesService } from './messages.service';

export class MessageDTO {
  telegramId: number;
  prompt: string;
  model: string;
}

@Controller('messages')
export class MessagesController {
  constructor(private messagesService: MessagesService) {}

  @Post()
  createMessage(@Body() dto: MessageDTO) {
    return this.messagesService.sentUserMessage(dto);
  }
}
