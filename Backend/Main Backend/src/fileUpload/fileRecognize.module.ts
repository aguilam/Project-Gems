import { Module } from '@nestjs/common';
import { FileRecognizeService } from './fileRecognize.service';

@Module({
  exports: [FileRecognizeService],
  providers: [FileRecognizeService],
})
export class FileRecognizeModule {}
