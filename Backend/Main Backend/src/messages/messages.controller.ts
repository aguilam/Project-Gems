import {
  Body,
  Controller,
  Post,
  UploadedFile,
  UseInterceptors,
} from '@nestjs/common';
import { MessagesService } from './messages.service';
import { memoryStorage } from 'multer';
import { FileInterceptor } from '@nestjs/platform-express';
export interface FileDTO {
  buffer: string;
  name: string;
  mime: string;
}

export class MessageDTO {
  telegramId: string;
  prompt: string;
  image?: string;
  file?: FileDTO;
  isForwarded?: string;
  chatId?: string;
}

@Controller('messages')
export class MessagesController {
  constructor(private messagesService: MessagesService) {}
  @Post()
  @UseInterceptors(
    FileInterceptor('file', {
      storage: memoryStorage(),
      limits: { fileSize: 10 * 1024 * 1024 },
    }),
  )
  async createMessage(
    @Body() dto: MessageDTO,
    @UploadedFile() uploadedFile?: Express.Multer.File,
  ) {
    if (uploadedFile) {
      const file: FileDTO = {
        buffer: uploadedFile.buffer.toString('base64'),
        name: uploadedFile.originalname,
        mime: uploadedFile.mimetype,
      };
      return await this.messagesService.sentUserMessage({
        telegramId: String(dto.telegramId),
        prompt: dto.prompt,
        image: dto.image,
        file: file,
        isForwarded: Boolean(dto.isForwarded),
        chatId: dto.chatId,
      });
    } else {
      return await this.messagesService.sentUserMessage({
        telegramId: String(dto.telegramId),
        prompt: dto.prompt,
        image: dto.image,
        chatId: dto.chatId,
      });
    }
  }
}
