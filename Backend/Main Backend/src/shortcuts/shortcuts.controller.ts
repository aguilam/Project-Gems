import {
  Body,
  Controller,
  Delete,
  Get,
  Param,
  Post,
  Query,
} from '@nestjs/common';
import { ShortcutsService } from './shortcuts.service';

@Controller('shortcuts')
export class ShortcutsController {
  constructor(private shortcutService: ShortcutsService) {}

  @Post()
  async postShortcut(
    @Body()
    dto: {
      instruction: string;
      command: string;
      modelId: string;
      telegramId: number;
    },
  ) {
    const shortcut = await this.shortcutService.postNewShortcut(dto);
    return shortcut;
  }

  @Get()
  async getUserShortcuts(@Query('telegramId') telegramId: number) {
    const userShortcuts =
      await this.shortcutService.getShortcutsByTelegramId(+telegramId);
    return userShortcuts;
  }

  @Delete(':id')
  async deleteUserShortcut(@Param('id') id: string) {
    await this.shortcutService.deleteShortcutsById(id);
  }
}
