import { Module } from '@nestjs/common';
import { fileRecognizeService } from './fileRecognize.service';

@Module({
  exports: [fileRecognizeService],
  providers: [fileRecognizeService],
})
export class FileRecognizeModule {}
