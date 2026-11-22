import type { ButtonHTMLAttributes, Ref } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost";

/** Buttons: 36 px tall (32 px small), always ≥24 px targets; disabled state keeps contrast. */
export function Button({
  variant = "primary",
  size = "md",
  className = "",
  type = "button",
  ref,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "sm" | "md";
  ref?: Ref<HTMLButtonElement>;
}) {
  return <button ref={ref} type={type} className={`btn btn-${variant} btn-${size} ${className}`.trim()} {...rest} />;
}
