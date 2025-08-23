import { Controller, Get } from '@nestjs/common';
import { ModelsService } from './models.service';
export class ChatCreateDto {
  telegramId: string;
}
@Controller('models')
export class ModelsController {
  constructor(private modelsService: ModelsService) {}

  @Get()
  getModels() {
    return this.modelsService.getAllModels();
  }
}
