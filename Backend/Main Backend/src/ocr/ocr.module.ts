import { Module } from '@nestjs/common';
import { OcrService } from './ocr.service';

@Module({
  exports: [OcrService],
  providers: [OcrService],
})
export class OcrModule {}
