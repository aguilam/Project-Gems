/*
  Warnings:

  - Added the required column `kind` to the `Subscription` table without a default value. This is not possible if the table is not empty.

*/
-- CreateEnum
CREATE TYPE "SubscriptionKind" AS ENUM ('TRIAL', 'PAID');

-- AlterTable
ALTER TABLE "Subscription" ADD COLUMN     "kind" "SubscriptionKind" NOT NULL,
ALTER COLUMN "telegramPaymentId" DROP NOT NULL,
ALTER COLUMN "providerPaymentId" DROP NOT NULL;
