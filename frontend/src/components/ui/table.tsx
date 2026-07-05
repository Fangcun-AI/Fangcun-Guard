import * as React from "react"

import { cn } from "@/lib/utils"

const withClassName = <Element extends HTMLElement, Props extends React.HTMLAttributes<Element>>(
  displayName: string,
  tagName: keyof React.JSX.IntrinsicElements,
  baseClassName: string
) => {
  const Component = React.forwardRef<Element, Props>(({ className, ...props }, ref) =>
    React.createElement(tagName, {
      ...props,
      ref,
      className: cn(baseClassName, className),
    })
  )
  Component.displayName = displayName
  return Component
}

const Table = React.forwardRef<
  HTMLTableElement,
  React.HTMLAttributes<HTMLTableElement>
>(({ className, ...props }, ref) => (
  <div className="relative w-full">
    <table
      ref={ref}
      className={cn("w-full caption-bottom text-sm", className)}
      {...props}
    />
  </div>
))
Table.displayName = "Table"

const TableHeader = withClassName<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>("TableHeader", "thead", "[&_tr]:border-b")

const TableBody = withClassName<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>("TableBody", "tbody", "[&_tr:last-child]:border-0")

const TableFooter = withClassName<
  HTMLTableSectionElement,
  React.HTMLAttributes<HTMLTableSectionElement>
>("TableFooter", "tfoot", "border-t bg-muted/50 font-medium [&>tr]:last:border-b-0")

const TableRow = withClassName<
  HTMLTableRowElement,
  React.HTMLAttributes<HTMLTableRowElement>
>("TableRow", "tr", "border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted")

const TableHead = React.forwardRef<
  HTMLTableCellElement,
  React.ThHTMLAttributes<HTMLTableCellElement>
>(({ className, ...props }, ref) => (
  <th
    ref={ref}
    className={cn(
      "h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0",
      className
    )}
    {...props}
  />
))
TableHead.displayName = "TableHead"

const TableCell = withClassName<
  HTMLTableCellElement,
  React.TdHTMLAttributes<HTMLTableCellElement>
>("TableCell", "td", "p-4 align-middle [&:has([role=checkbox])]:pr-0")

const TableCaption = withClassName<
  HTMLTableCaptionElement,
  React.HTMLAttributes<HTMLTableCaptionElement>
>("TableCaption", "caption", "mt-4 text-sm text-muted-foreground")

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}
