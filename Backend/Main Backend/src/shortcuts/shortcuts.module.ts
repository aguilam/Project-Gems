import { Module } from '@nestjs/common';
import { ShortcutsService } from './shortcuts.service';
import { ShortcutsController } from './shortcuts.controller';

@Module({
  exports: [],
  controllers: [ShortcutsController],
  providers: [ShortcutsService],
})
export class ShortcutsModule {}
