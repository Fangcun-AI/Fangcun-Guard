import * as React from 'react'
import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
  type ColumnDef,
  type PaginationState,
} from '@tanstack/react-table'
import { ChevronLeft, ChevronRight } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
  pageCount?: number
  currentPage?: number
  pageSize?: number
  onPageChange?: (page: number) => void
  onPageSizeChange?: (pageSize: number) => void
  loading?: boolean
  pagination?: boolean
  emptyMessage?: string
  fillHeight?: boolean
  stickyLastColumn?: boolean
}

const pageSizes = [10, 20, 30, 50, 100]

export function DataTable<TData, TValue>({
  columns,
  data,
  pageCount = 0,
  currentPage = 1,
  pageSize = 10,
  onPageChange,
  onPageSizeChange,
  loading = false,
  pagination = true,
  emptyMessage = 'No results found.',
  fillHeight = false,
  stickyLastColumn = false,
}: DataTableProps<TData, TValue>) {
  const remote = Boolean(onPageChange)
  const [paging, setPaging] = React.useState<PaginationState>({ pageIndex: currentPage - 1, pageSize })

  React.useEffect(() => {
    if (remote) setPaging({ pageIndex: currentPage - 1, pageSize })
  }, [currentPage, pageSize, remote])

  const table = useReactTable({
    columns,
    data,
    pageCount: remote ? pageCount : undefined,
    state: { pagination: paging },
    onPaginationChange: setPaging,
    getCoreRowModel: getCoreRowModel(),
    ...(remote ? { manualPagination: true } : { getPaginationRowModel: getPaginationRowModel() }),
  })
  const rows = table.getRowModel().rows
  const activePage = remote ? currentPage : paging.pageIndex + 1
  const totalPages = remote ? pageCount || 1 : Math.ceil(data.length / paging.pageSize)
  const lastColumn = (index: number, count: number) => stickyLastColumn && index === count - 1
  const stickyStyle = (header = false): React.CSSProperties => ({ position: 'sticky', right: 0, zIndex: header ? 2 : 1 })

  const changePage = (nextPage: number) => {
    if (remote) onPageChange?.(nextPage)
    else setPaging((previous) => ({ ...previous, pageIndex: nextPage - 1 }))
  }
  const changePageSize = (value: string) => {
    const nextSize = Number(value)
    setPaging({ pageIndex: 0, pageSize: nextSize })
    if (remote) {
      onPageSizeChange?.(nextSize)
      onPageChange?.(1)
    }
  }

  return (
    <div className={fillHeight ? 'flex h-full flex-col' : 'space-y-4'}>
      <div className={`${fillHeight ? 'flex-1 overflow-auto border-t' : 'rounded-md border'} ${stickyLastColumn ? 'overflow-x-auto' : ''}`}>
        <Table className={stickyLastColumn ? 'min-w-max table-auto' : ''}>
          <TableHeader>
            {table.getHeaderGroups().map((group) => <TableRow key={group.id}>
              {group.headers.map((header, index) => {
                const sticky = lastColumn(index, group.headers.length)
                return <TableHead key={header.id} style={sticky ? stickyStyle(true) : undefined} className={sticky ? 'bg-muted shadow-[-4px_0_8px_-4px_rgba(0,0,0,0.1)]' : ''}>
                  {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                </TableHead>
              })}
            </TableRow>)}
          </TableHeader>
          <TableBody>
            {loading ? <TableRow><TableCell colSpan={columns.length} className="h-24 text-center"><div className="flex items-center justify-center"><div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" /></div></TableCell></TableRow>
              : rows.length ? rows.map((row) => <TableRow key={row.id} data-state={row.getIsSelected() ? 'selected' : undefined}>
                {row.getVisibleCells().map((cell, index) => {
                  const sticky = lastColumn(index, row.getVisibleCells().length)
                  return <TableCell key={cell.id} style={sticky ? stickyStyle() : undefined} className={sticky ? '!bg-zinc-900 shadow-[-4px_0_8px_-4px_rgba(0,0,0,0.3)]' : ''}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                })}
              </TableRow>)
                : <TableRow><TableCell colSpan={columns.length} className="h-24 text-center">{emptyMessage}</TableCell></TableRow>}
          </TableBody>
        </Table>
      </div>
      {pagination && totalPages > 0 && <div className={fillHeight ? 'flex flex-shrink-0 items-center justify-between border-t border-zinc-800 bg-zinc-900 px-2 py-4' : 'flex items-center justify-between px-2'}>
        <div className="flex items-center space-x-2">
          <p className="text-sm font-medium">Rows per page</p>
          <Select value={`${paging.pageSize}`} onValueChange={changePageSize}>
            <SelectTrigger className="h-8 w-[70px]"><SelectValue placeholder={paging.pageSize} /></SelectTrigger>
            <SelectContent side="top">{pageSizes.map((size) => <SelectItem key={size} value={`${size}`}>{size}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="flex items-center space-x-6 lg:space-x-8">
          <div className="flex w-[100px] items-center justify-center text-sm font-medium">Page {activePage} of {totalPages}</div>
          <div className="flex items-center space-x-2">
            <Button variant="outline" className="h-8 w-8 p-0" onClick={() => changePage(activePage - 1)} disabled={activePage <= 1 || loading}><span className="sr-only">Go to previous page</span><ChevronLeft className="h-4 w-4" /></Button>
            <Button variant="outline" className="h-8 w-8 p-0" onClick={() => changePage(activePage + 1)} disabled={activePage >= totalPages || loading}><span className="sr-only">Go to next page</span><ChevronRight className="h-4 w-4" /></Button>
          </div>
        </div>
      </div>}
    </div>
  )
}
