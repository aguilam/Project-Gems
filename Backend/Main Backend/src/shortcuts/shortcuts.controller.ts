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
      telegramId: string;
    },
  ) {
    const shortcut = await this.shortcutService.postNewShortcut(dto);
    return shortcut;
  }

  @Get()
  async getUserShortcuts(@Query('telegramId') telegramId: string) {
    const userShortcuts = await this.shortcutService.getShortcutsByTelegramId(
      String(telegramId),
    );
    return userShortcuts;
  }

  @Get(':id')
  async getShortcutById(@Param('id') id: string) {
    const shortcut = await this.shortcutService.getShortcutById(id);
    return shortcut;
  }
  @Delete(':id')
  async deleteShortcutById(@Param('id') id: string) {
    await this.shortcutService.deleteShortcutsById(id);
  }

  @Patch(':id')
  async patchShortcutById(
    @Param('id') id: string,
    @Body()
    dto: {
      command?: string;
      modelId?: string;
      instruction?: string;
    },
  ) {
    const fullDto = { id, ...dto };
    return await this.shortcutService.patchShortcutById(fullDto);
  }
}
