import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  Post,
  Query,
} from '@nestjs/common';
import { ChatsService } from './chats.service';
export class ChatCreateDto {
  telegramId: number;
}
@Controller('chats')
export class ChatsController {
  constructor(private chatsService: ChatsService) {}

  @Post()
  createChat(@Body() dto: ChatCreateDto) {
    return this.chatsService.createChat(dto);
  }

  @Get()
  getChats(@Query('telegramId') telegramId: number) {
    return this.chatsService.getAllChats(+telegramId);
  }

  @Delete(':id')
  deleteChat(@Param('id') id: string) {
    return this.chatsService.deleteChat(id);
  }
}
