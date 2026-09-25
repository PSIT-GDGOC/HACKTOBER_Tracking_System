import React, { Component } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Callout, LinkButton, Panel } from "@/components/ui";

/* ================================================================== */
/*  404                                                                */
/* ================================================================== */

export function NotFound() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center px-4 py-16 text-center">
      <div className="relative">
        <p className="font-display text-[26vw] font-extrabold leading-none tracking-tighter sm:text-[180px]">
          <span className="text-gblue">4</span>
          <span className="text-gred">0</span>
          <span className="text-gyellow">4</span>
        </p>
        <span className="absolute -right-4 top-2 rotate-12">
          <span className="inline-block border-[3px] border-ink bg-ggreen px-3 py-1 font-display text-xs font-extrabold uppercase text-white shadow-[4px_4px_0_0_#101010]">
            not found
          </span>
        </span>
      </div>
      <p className="mt-4 max-w-md font-display text-xl font-extrabold uppercase">
        This page went to a repo that doesn't exist
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <LinkButton to="/dashboard" variant="blue">← Back to dashboard</LinkButton>
        <LinkButton to="/dashboard/issues" variant="paper">Browse issues</LinkButton>
        <LinkButton to="/" variant="yellow">Home</LinkButton>
      </div>
    </div>
  );
}

/* ================================================================== */
/*  403                                                                */
/* ================================================================== */

export function Forbidden() {
  const { user } = useAuth();
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center px-4 py-16 text-center">
      <Panel className="border-[4px] border-ink bg-gred p-6 shadow-[10px_10px_0_0_#101010]">
        <p className="font-display text-[24vw] font-extrabold leading-none text-white sm:text-[140px]">403</p>
      </Panel>
      <p className="mt-6 font-display text-2xl font-extrabold uppercase">Maintainers only past this point</p>
      <p className="mt-2 max-w-lg text-sm text-ink-soft">
        You're signed in as <b>{user?.role ?? "guest"}</b>. This area needs a different role — ask a
        chapter admin to update your permissions.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <LinkButton to="/dashboard" variant="blue">← Back to dashboard</LinkButton>
      </div>
      <div className="mt-8 max-w-xl">
        <Callout tone="yellow" title="Role guards">
          Routes are wrapped in <code className="font-mono">RequireRole</code> on the client, and the
          backend enforces the same rules with role middleware on every endpoint.
        </Callout>
      </div>
    </div>
  );
}

/** Shared error boundary — catches render crashes anywhere in the tree. */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-[70vh] flex-col items-center justify-center px-4 py-16 text-center">
          <Panel className="max-w-xl p-6 text-left">
            <p className="font-display text-lg font-extrabold uppercase">▲ Something broke</p>
            <p className="mt-2 break-words font-mono text-xs text-ink-soft">
              {String(this.state.error?.message || this.state.error)}
            </p>
            <div className="mt-4 flex gap-2">
              <LinkButton to="/dashboard" variant="blue">← Dashboard</LinkButton>
              <a
                href={window.location.href}
                className="inline-flex items-center border-[3px] border-ink bg-white px-4 py-2.5 font-display text-sm font-bold uppercase shadow-[4px_4px_0_0_#101010]"
              >
                Reload
              </a>
            </div>
          </Panel>
        </div>
      );
    }
    return this.props.children;
  }
}

/** Footer link helper used by the landing page. */
export function FooterLink({ to, children }) {
  return <Link to={to} className="hover:text-gblue">{children}</Link>;
}
