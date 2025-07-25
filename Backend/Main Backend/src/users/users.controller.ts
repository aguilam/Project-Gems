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
  telegramId: number;
  username?: string;
}

@Controller('user')
export class usersController {
  constructor(private usersService: UsersService) {}

  @Post()
  login(@Body() dto: LoginDto) {
    return this.usersService.login(dto);
  }

  @Get(':telegramId')
  getUser(@Param('telegramId', ParseIntPipe) telegramId: number) {
    return this.usersService.getUserByTelegramId(telegramId);
  }

  @Patch()
  patchUser(@Body() dto: any) {
    return this.usersService.updateUserInfo(dto);
  }
}
