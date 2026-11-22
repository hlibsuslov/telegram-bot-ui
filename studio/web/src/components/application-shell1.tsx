// Adapted from the shadcnblocks block application-shell1 (see SHADCNBLOCKS.md): the sidebar,
// grouped navigation with submenus, footer and breadcrumb header are the block's; the brand,
// account menu and demo data are replaced by the bot-ui project, its revision and drafts.
import { ChevronRight, type LucideIcon } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";

export type NavItem = {
  key: string;
  label: string;
  icon: LucideIcon;
  href: string;
  badge?: string | number;
  children?: { key: string; label: string; href: string }[];
};

export type NavGroup = { title: string; items: NavItem[] };
export type Crumb = { label: string; href?: string };

export interface ApplicationShell1Props {
  className?: string;
  /** Project block in the sidebar header (name, revision chip, changes indicator). */
  brand: React.ReactNode;
  navGroups: NavGroup[];
  footer?: React.ReactNode;
  active: string;
  trail: Crumb[];
  headerEnd?: React.ReactNode;
  mobileTitle: string;
  children: React.ReactNode;
}

const buttonMotion =
  "transition-[width,height,padding,background-color,color,transform] duration-200 ease-out active:scale-[0.98] motion-reduce:transition-none motion-reduce:active:scale-100";

function CloseOnNavigate({ children }: { children: React.ReactNode }) {
  const { isMobile, setOpenMobile } = useSidebar();
  return <div onClick={(e) => { if (isMobile && (e.target as HTMLElement).closest("a")) setOpenMobile(false); }}>{children}</div>;
}

const NavMenuItem = ({ item, active }: { item: NavItem; active: string }) => {
  const Icon = item.icon;
  const isActive = active === item.key;
  const badge = item.badge !== undefined && item.badge !== 0 ? <SidebarMenuBadge>{item.badge}</SidebarMenuBadge> : null;
  if (!item.children?.length) {
    return (
      <SidebarMenuItem>
        <SidebarMenuButton asChild isActive={isActive} className={buttonMotion} tooltip={item.label}>
          <a href={item.href} aria-current={isActive ? "page" : undefined}>
            <Icon className="size-4" />
            <span>{item.label}</span>
          </a>
        </SidebarMenuButton>
        {badge}
      </SidebarMenuItem>
    );
  }
  return (
    <Collapsible asChild defaultOpen className="group/collapsible">
      <SidebarMenuItem>
        <SidebarMenuButton asChild isActive={isActive} className={cn(buttonMotion, "pr-8")} tooltip={item.label}>
          <a href={item.href} aria-current={isActive ? "page" : undefined}>
            <Icon className="size-4" />
            <span>{item.label}</span>
          </a>
        </SidebarMenuButton>
        <CollapsibleTrigger
          className="absolute top-1.5 right-1 flex size-5 items-center justify-center rounded-md text-muted-foreground hover:bg-sidebar-accent group-data-[collapsible=icon]:hidden"
          aria-label={`Show or hide the ${item.label} list`}
        >
          <ChevronRight className="size-4 transition-transform duration-300 group-data-[state=open]/collapsible:rotate-90 motion-reduce:transition-none" />
        </CollapsibleTrigger>
        <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down motion-reduce:animate-none">
          <SidebarMenuSub>
            {item.children.map((child) => {
              const childActive = active === `${item.key}:${child.key}`;
              return (
                <SidebarMenuSubItem key={child.key}>
                  <SidebarMenuSubButton asChild isActive={childActive} className={buttonMotion}>
                    <a href={child.href} aria-current={childActive ? "page" : undefined}>
                      <span className="font-mono text-xs">{child.label}</span>
                    </a>
                  </SidebarMenuSubButton>
                </SidebarMenuSubItem>
              );
            })}
          </SidebarMenuSub>
        </CollapsibleContent>
      </SidebarMenuItem>
    </Collapsible>
  );
};

const AppSidebar = ({ brand, navGroups, footer, active }: Pick<ApplicationShell1Props, "brand" | "navGroups" | "footer" | "active">) => (
  <Sidebar collapsible="icon">
    <SidebarHeader>{brand}</SidebarHeader>
    <SidebarContent className="overflow-hidden">
      <ScrollArea className="min-h-0 flex-1">
        <CloseOnNavigate>
          {navGroups.map((group) => (
            <SidebarGroup key={group.title}>
              <SidebarGroupLabel>{group.title}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {group.items.map((item) => <NavMenuItem key={item.key} item={item} active={active} />)}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))}
        </CloseOnNavigate>
      </ScrollArea>
    </SidebarContent>
    {footer && <SidebarFooter>{footer}</SidebarFooter>}
    <SidebarRail />
  </Sidebar>
);

export function ApplicationShell1({ className, brand, navGroups, footer, active, trail, headerEnd, mobileTitle, children }: ApplicationShell1Props) {
  return (
    <SidebarProvider className={cn(className)}>
      <AppSidebar brand={brand} navGroups={navGroups} footer={footer} active={active} />
      <SidebarInset className="min-w-0">
        <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b bg-background px-3 sm:px-4">
          <SidebarTrigger className="-ml-1" aria-label="Toggle navigation" />
          <Separator orientation="vertical" className="mx-1 hidden h-5 md:block" />
          <span className="truncate text-sm font-semibold md:hidden">{mobileTitle}</span>
          <Breadcrumb className="hidden min-w-0 md:block">
            <BreadcrumbList className="flex-nowrap">
              {trail.map((crumb, index) => {
                const isLast = index === trail.length - 1;
                return (
                  <React.Fragment key={`${crumb.label}-${index}`}>
                    {index > 0 && <BreadcrumbSeparator />}
                    <BreadcrumbItem className="min-w-0">
                      {isLast || !crumb.href ? (
                        <BreadcrumbPage className="truncate">{crumb.label}</BreadcrumbPage>
                      ) : (
                        <BreadcrumbLink href={crumb.href}>{crumb.label}</BreadcrumbLink>
                      )}
                    </BreadcrumbItem>
                  </React.Fragment>
                );
              })}
            </BreadcrumbList>
          </Breadcrumb>
          <div className="ml-auto flex shrink-0 items-center gap-1">{headerEnd}</div>
        </header>
        <div className="flex min-h-0 flex-1 flex-col">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}
