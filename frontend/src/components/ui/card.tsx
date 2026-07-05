import * as React from "react"

import { cn } from "@/lib/utils"

type DivProps = React.HTMLAttributes<HTMLDivElement>

const createCardBlock = (displayName: string, baseClassName: string) => {
  const Component = React.forwardRef<HTMLDivElement, DivProps>(
    ({ className, ...props }, ref) => (
      <div ref={ref} className={cn(baseClassName, className)} {...props} />
    )
  )
  Component.displayName = displayName
  return Component
}

const Card = createCardBlock(
  "Card",
  "rounded-xl border bg-card text-card-foreground shadow-elevation-2 transition-all duration-300 hover:shadow-elevation-4 hover:-translate-y-0.5 hover:border-primary/15"
)

const CardHeader = createCardBlock("CardHeader", "flex flex-col space-y-1.5 p-6")

const CardTitle = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn(
      "text-2xl font-semibold leading-none tracking-tight",
      className
    )}
    {...props}
  />
))
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props}
  />
))
CardDescription.displayName = "CardDescription"

const CardContent = createCardBlock("CardContent", "p-6 pt-0")

const CardFooter = createCardBlock("CardFooter", "flex items-center p-6 pt-0")

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
