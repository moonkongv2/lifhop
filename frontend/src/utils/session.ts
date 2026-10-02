import { useSyncExternalStore } from "react";

const sessionEvent = "lifhop-session-change";
export const sessionExpiredMessage = "Your session has expired. Please log in again.";
export const getAccessToken = () => localStorage.getItem("access_token");

function subscribe(listener: () => void) {
  window.addEventListener(sessionEvent, listener);
  window.addEventListener("storage", listener);
  return () => { window.removeEventListener(sessionEvent, listener); window.removeEventListener("storage", listener); };
}
export function useAccessToken() {
  return useSyncExternalStore(subscribe, getAccessToken);
}
export function setAccessToken(token: string) {
  sessionStorage.removeItem("session_notice");
  localStorage.removeItem("refresh_token");
  localStorage.setItem("access_token", token);
  window.dispatchEvent(new Event(sessionEvent));
}
export function clearSession(expired = false) {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  if (expired) sessionStorage.setItem("session_notice", sessionExpiredMessage);
  else sessionStorage.removeItem("session_notice");
  window.dispatchEvent(new Event(sessionEvent));
}
export function expireSession(token: string) {
  if (getAccessToken() === token) clearSession(true);
}
export function assertCurrentSession(token: string) {
  if (getAccessToken() !== token) throw new Error("Your session has changed. Please log in again.");
}
