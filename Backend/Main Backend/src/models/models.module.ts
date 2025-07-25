import { Module } from '@nestjs/common';
import { ModelsController } from './models.controller';
import { ModelsService } from './models.service';

@Module({
  exports: [],
  controllers: [ModelsController],
  providers: [ModelsService],
})
export class ModelsModule {}
