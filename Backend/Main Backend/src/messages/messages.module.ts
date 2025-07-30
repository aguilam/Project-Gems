import { Module } from '@nestjs/common';
import { MessagesController } from './messages.controller';
import { MessagesService } from './messages.service';
import { ChatsModule } from 'src/chats/chats.module';
import { OcrModule } from 'src/ocr/ocr.module';
import { FileRecognizeModule } from 'src/fileUpload/fileRecognize.module';

@Module({
  imports: [ChatsModule, OcrModule, FileRecognizeModule],
  controllers: [MessagesController],
  providers: [MessagesService],
})
export class MessagesModule {}
