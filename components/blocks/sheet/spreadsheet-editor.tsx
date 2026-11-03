"use client";

import { parse, unparse } from "papaparse";
import type { CSSProperties } from "react";
import { memo, useEffect, useMemo, useState } from "react";
import { DataGrid, textEditor } from "react-data-grid";
import type { SortColumn } from "react-data-grid";

import { cn } from "@/lib/utils";

import "react-data-grid/lib/styles.css";

interface SheetEditorProps {
  content: string;
  saveContent: (content: string, isCurrentVersion: boolean) => void;
  currentVersionIndex: number;
  isCurrentVersion: boolean;
  status: string;
}

const MIN_ROWS = 50;
const MIN_COLS = 26;

const PureSpreadsheetEditor = ({
  content,
  saveContent,
  isCurrentVersion,
}: SheetEditorProps) => {
  const resolvedTheme: string = "light";
  const [sortColumns, setSortColumns] = useState<readonly SortColumn[]>([]);

  const parseData = useMemo(() => {
    if (!content) {
      return new Array(MIN_ROWS).fill(new Array(MIN_COLS).fill(""));
    }

    const result = parse<string[]>(content, { skipEmptyLines: true });

    const paddedData = result.data.map((row) => {
      const paddedRow = [...row];
      while (paddedRow.length < MIN_COLS) {
        paddedRow.push("");
      }
      return paddedRow;
    });

    while (paddedData.length < MIN_ROWS) {
      paddedData.push(new Array(MIN_COLS).fill(""));
    }

    return paddedData;
  }, [content]);

  const columns = useMemo(() => {
    const rowNumberColumn = {
      cellClass:
        "border-border border-r border-t bg-muted/35 text-muted-foreground tabular-nums text-xs",
      frozen: true,
      headerCellClass:
        "border-border border-r border-t bg-muted/80 font-medium text-muted-foreground text-xs",
      key: "rowNumber",
      name: "",
      renderCell: ({ rowIdx }: { rowIdx: number }) => rowIdx + 1,
      width: 44,
    };

    const dataColumns = Array.from({ length: MIN_COLS }, (_, i) => ({
      cellClass: cn(
        "border-t border-border bg-background text-[13px] text-foreground",
        {
          "border-l": i !== 0,
        }
      ),
      headerCellClass: cn(
        "border-t border-border bg-muted/90 text-xs font-medium text-foreground tabular-nums",
        {
          "border-l": i !== 0,
        }
      ),
      key: i.toString(),
      name: String.fromCharCode(65 + i),
      renderEditCell: textEditor,
      width: 140,
    }));

    return [rowNumberColumn, ...dataColumns];
  }, []);

  const initialRows = useMemo(
    () =>
      parseData.map((row, rowIndex) => {
        const rowData: Record<string, string | number> = {
          id: rowIndex,
          rowNumber: rowIndex + 1,
        };

        columns.slice(1).forEach((col, colIndex) => {
          rowData[col.key] = row[colIndex] || "";
        });

        return rowData;
      }),
    [parseData, columns]
  );

  const [localRows, setLocalRows] = useState(initialRows);

  useEffect(() => {
    setLocalRows(initialRows);
  }, [initialRows]);

  const sortedRows = useMemo(() => {
    if (sortColumns.length === 0) {
      return localRows;
    }

    const headerRow = localRows[0];
    const dataRows = localRows.slice(1);

    const sortedDataRows = [...dataRows].sort((rowA, rowB) => {
      for (const sort of sortColumns) {
        const comparator = (
          a: Record<string, string | number>,
          b: Record<string, string | number>
        ) => {
          const aVal = a[sort.columnKey];
          const bVal = b[sort.columnKey];

          if (aVal === "" && bVal === "") {
            return 0;
          }
          if (aVal === "") {
            return sort.direction === "ASC" ? 1 : -1;
          }
          if (bVal === "") {
            return sort.direction === "ASC" ? -1 : 1;
          }

          const aNum = Number.parseFloat(String(aVal));
          const bNum = Number.parseFloat(String(bVal));

          const aIsNumber = !Number.isNaN(aNum);
          const bIsNumber = !Number.isNaN(bNum);
          const bothAreNumbers = aIsNumber && bIsNumber;

          if (bothAreNumbers) {
            return sort.direction === "ASC" ? aNum - bNum : bNum - aNum;
          }

          const aStr = String(aVal).toLowerCase();
          const bStr = String(bVal).toLowerCase();

          if (aStr < bStr) {
            return sort.direction === "ASC" ? -1 : 1;
          }
          if (aStr > bStr) {
            return sort.direction === "ASC" ? 1 : -1;
          }
          return 0;
        };

        const result = comparator(rowA, rowB);
        if (result !== 0) {
          return result;
        }
      }
      return 0;
    });

    return [headerRow, ...sortedDataRows];
  }, [localRows, sortColumns]);

  const generateCsv = (data: string[][]) => unparse(data);

  const handleRowsChange = (newRows: Record<string, string | number>[]) => {
    if (!isCurrentVersion) {
      return;
    }
    setLocalRows(newRows);

    const updatedData = newRows.map((row) =>
      columns.slice(1).map((col) => String(row[col.key] || ""))
    );

    const newCsvContent = generateCsv(updatedData);
    saveContent(newCsvContent, true);
  };

  const handleSortColumnsChange = (newSortColumns: readonly SortColumn[]) => {
    setSortColumns(newSortColumns);
  };

  const gridStyle = {
    "--rdg-background-color": "var(--background)",
    "--rdg-border-color": "var(--border)",
    "--rdg-border-width": "1px",
    "--rdg-cell-frozen-box-shadow":
      resolvedTheme === "dark"
        ? "3px 0 12px -4px rgba(0,0,0,0.45)"
        : "3px 0 10px -4px rgba(0,0,0,0.08)",
    "--rdg-cell-padding": "6px 10px",
    "--rdg-color": "var(--foreground)",
    "--rdg-font-size": "13px",
    "--rdg-header-background-color": "var(--muted)",
    "--rdg-header-draggable-background-color": "var(--muted)",
    "--rdg-line-height": "1.45",
    "--rdg-row-hover-background-color":
      "color-mix(in oklch, var(--accent) 32%, transparent)",
    "--rdg-row-selected-background-color":
      "color-mix(in oklch, var(--primary) 16%, transparent)",
    "--rdg-row-selected-hover-background-color":
      "color-mix(in oklch, var(--primary) 24%, transparent)",
    "--rdg-selection-color": "var(--ring)",
    "--rdg-selection-width": "2px",
    height: "100%",
  } as CSSProperties;

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden bg-muted/25 p-2 sm:p-3">
      {status === "streaming" ? (
        <div
          aria-live="polite"
          className="mb-2 flex shrink-0 items-center gap-2 rounded-[calc(var(--radius)+2px)] border border-primary/20 bg-primary/5 px-3 py-1.5 text-[11px] tracking-[0.08em] text-muted-foreground uppercase"
        >
          <span className="size-1.5 shrink-0 animate-pulse rounded-full bg-primary motion-reduce:animate-none" />
          Streaming updates
        </div>
      ) : null}
      <div
        className={cn(
          "relative min-h-0 flex-1 overflow-hidden rounded-[calc(var(--radius)+6px)] bg-background",
          "shadow-[0px_0px_0px_1px_rgba(0,0,0,0.06),0px_1px_2px_-1px_rgba(0,0,0,0.06),0px_4px_12px_-2px_rgba(0,0,0,0.06)]",
          "dark:shadow-[0px_0px_0px_1px_rgba(255,255,255,0.06),0px_1px_2px_-1px_rgba(255,255,255,0.04),0px_4px_14px_-2px_rgba(0,0,0,0.35)]",
          "[outline:1px_solid_rgba(0,0,0,0.05)] dark:[outline-color:rgba(255,255,255,0.07)]"
        )}
      >
        <DataGrid
          className={resolvedTheme === "dark" ? "rdg-dark" : "rdg-light"}
          columns={columns}
          defaultColumnOptions={{
            resizable: isCurrentVersion,
            sortable: true,
          }}
          enableVirtualization
          onCellClick={(args) => {
            if (args.column.key !== "rowNumber") {
              args.selectCell(true);
            }
          }}
          onRowsChange={handleRowsChange}
          onSortColumnsChange={handleSortColumnsChange}
          rows={sortedRows}
          sortColumns={sortColumns}
          style={gridStyle}
        />
      </div>
    </div>
  );
};

function areEqual(prevProps: SheetEditorProps, nextProps: SheetEditorProps) {
  return (
    prevProps.currentVersionIndex === nextProps.currentVersionIndex &&
    prevProps.isCurrentVersion === nextProps.isCurrentVersion &&
    prevProps.status === nextProps.status &&
    !(prevProps.status === "streaming" && nextProps.status === "streaming") &&
    prevProps.content === nextProps.content &&
    prevProps.saveContent === nextProps.saveContent
  );
}

export const SpreadsheetEditor = memo(PureSpreadsheetEditor, areEqual);
