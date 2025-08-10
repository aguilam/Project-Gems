import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  Patch,
  Post,
  Query,
} from '@nestjs/common';
import { ChatsService } from './chats.service';
export class ChatCreateDto {
  userId: string;
  title: string;
}
@Controller('chats')
export class ChatsController {
  constructor(private chatsService: ChatsService) {}

  @Post()
  createChat(@Body() dto: ChatCreateDto) {
    return this.chatsService.createChat(dto.userId, dto.title);
  }

  @Get()
  getChats(@Query('telegramId') telegramId: number) {
    return this.chatsService.getAllChats(+telegramId);
  }

  @Delete(':id')
  deleteChat(@Param('id') id: string) {
    return this.chatsService.deleteChat(id);
  }

  @Patch(':id')
  editChat(@Param('id') id: string, @Body() dto: { title: string }) {
    return this.chatsService.editChat({ id, title: dto.title });
  }
}
