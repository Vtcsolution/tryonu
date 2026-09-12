import type { Metadata } from "next";
import { ForgotPasswordForm } from "./ForgotPasswordForm";

export const metadata: Metadata = {
  title: "Reset your password",
  description: "Get a password reset link for your TryOnU account.",
};

export default function ForgotPasswordPage() {
  return <ForgotPasswordForm />;
}
