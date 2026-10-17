import type { Metadata } from "next";
import { ForgotPasswordForm } from "./ForgotPasswordForm";
import { PRIVATE_PAGE } from "@/lib/seo";

export const metadata: Metadata = {
  title: "Reset your password",
  description: "Get a password reset link for your TryOnU account.",
  robots: PRIVATE_PAGE,
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}
