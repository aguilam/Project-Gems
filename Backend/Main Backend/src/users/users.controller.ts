import {
  Body,
  Controller,
  Get,
  Patch,
  Post,
  Param,
  ParseIntPipe,
} from '@nestjs/common';
import { UsersService } from './users.service';
export class LoginDto {
  telegramId: string;
  username?: string;
}

export class UpdateUserDto {
  telegramId: string;
  userName?: string;
  systemPrompt?: string;
  defaultModelId?: string;
}

@Controller('user')
export class usersController {
  constructor(private usersService: UsersService) {}

  @Post()
  login(@Body() dto: LoginDto) {
    return this.usersService.login(dto);
  }

  @Get(':telegramId')
  getUser(@Param('telegramId', ParseIntPipe) telegramId: string) {
    return this.usersService.getUserByTelegramId(telegramId);
  }

  @Patch()
  patchUser(@Body() dto: UpdateUserDto) {
    return this.usersService.updateUserInfo(dto);
  }
}
