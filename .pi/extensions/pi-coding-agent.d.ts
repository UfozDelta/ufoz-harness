// Ambient shim: @earendil-works/pi-coding-agent isn't vendored in this repo's
// node_modules, only inside pi's own install. Types are `any` on purpose.
declare module "@earendil-works/pi-coding-agent" {
	export interface ExtensionAPI {
		on(event: string, callback: (event: any, ctx: any) => any): void;
	}
}
