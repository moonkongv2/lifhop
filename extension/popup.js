const captureButton = document.getElementById("capture");
const output = document.getElementById("output");

console.log("lifhop extension v0.2 loaded");

captureButton.addEventListener("click", async () => {
  output.textContent = "Reading conversation...";

  try {
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });

    if (!tab?.id) {
      throw new Error("Active tab not found");
    }

    const results = await chrome.scripting.executeScript({
      target: {
        tabId: tab.id,
      },
      func: collectChatGPTConversation,
    });

    const result = results[0]?.result;

    output.textContent = JSON.stringify(
      result,
      null,
      2,
    );
  } catch (error) {
    output.textContent = `Error: ${error.message}`;
  }
});


async function collectChatGPTConversation() {
  if (location.hostname !== "chatgpt.com") {
    throw new Error("ChatGPT 페이지가 아닙니다.");
  }

  const selector =
    '[data-message-author-role="user"], ' +
    '[data-message-author-role="assistant"]';

  const sleep = (ms) =>
    new Promise((resolve) => setTimeout(resolve, ms));

  const getMessages = () => [
    ...document.querySelectorAll(selector),
  ];

  const firstMessage = getMessages()[0];

  if (!firstMessage) {
    throw new Error("메시지 DOM을 찾지 못했습니다.");
  }

  // 실제 대화 스크롤 영역 찾기
  let scroller = firstMessage.parentElement;

  while (scroller) {
    const style = getComputedStyle(scroller);

    const isScrollable =
      /(auto|scroll)/.test(style.overflowY) &&
      scroller.scrollHeight > scroller.clientHeight + 20;

    if (isScrollable) break;

    scroller = scroller.parentElement;
  }

  scroller ??= document.scrollingElement;

  const originalTop = scroller.scrollTop;
  const originalBehavior = scroller.style.scrollBehavior;

  // 한 번에 화면 높이의 60%만 이동해
  // 인접 수집 구간이 겹치도록 한다.
  const step = Math.max(
    150,
    Math.floor(scroller.clientHeight * 0.6)
  );

  const collected = new Map();

  function extractAssistantMarkdown(root) {
    function renderInline(node) {
      if (node.nodeType === 3) {
        return node.textContent;
      }

      if (node.nodeType !== 1) return "";

      const tag = node.tagName.toLowerCase();

      // 코드블록의 버튼과 기타 UI 제외
      if (["button", "svg", "script", "style"].includes(tag)) {
        return "";
      }

      if (tag === "br") return "\n";

      if (tag === "code") {
        const value = node.textContent;
        const longest = Math.max(
          0,
          ...(value.match(/`+/g) ?? []).map((x) => x.length)
        );
        const ticks = "`".repeat(longest + 1);
        return `${ticks}${value}${ticks}`;
      }

      const content = [...node.childNodes]
        .map(renderInline)
        .join("");

      if (tag === "strong" || tag === "b") {
        return `**${content}**`;
      }

      if (tag === "em" || tag === "i") {
        return `*${content}*`;
      }

      return content;
    }

    function renderBlock(node) {
      if (node.nodeType === 3) {
        return node.textContent.trim();
      }

      if (node.nodeType !== 1) return "";

      const tag = node.tagName.toLowerCase();

      if (["button", "svg", "script", "style"].includes(tag)) {
        return "";
      }

      if (tag === "pre") {
        const code = node.querySelector("code") ?? node;

        const classNames = [
          code.getAttribute("class") ?? "",
          node.getAttribute("class") ?? "",
        ].join(" ");

        const language =
          code.getAttribute("data-language") ??
          node.getAttribute("data-language") ??
          classNames.match(/(?:language|lang)-([\w+#.-]+)/)?.[1] ??
          "";

        // textContent를 사용해야 코드의 들여쓰기와 줄바꿈을 보존한다.
        const source = code.textContent
          .replace(/\r\n?/g, "\n")
          .replace(/\n$/, "");

        const longest = Math.max(
          2,
          ...(source.match(/`{3,}/g) ?? []).map((x) => x.length)
        );

        const fence = "`".repeat(longest + 1);

        return `${fence}${language}\n${source}\n${fence}`;
      }

      // 코드블록을 감싼 div에 언어명, Run, Copy 등의
      // UI가 함께 있는 경우 pre만 추출한다.
      if (tag === "div" && node !== root) {
        const preElements = node.querySelectorAll("pre");

        const hasOtherBlocks = node.querySelector(
          "p, h1, h2, h3, h4, h5, h6, ul, ol, blockquote, table"
        );

        if (preElements.length === 1 && !hasOtherBlocks) {
          return renderBlock(preElements[0]);
        }
      }

      if (tag === "p") {
        return [...node.childNodes].map(renderInline).join("");
      }

      if (/^h[1-6]$/.test(tag)) {
        const level = Number(tag[1]);
        return `${"#".repeat(level)} ${renderInline(node)}`;
      }

      if (tag === "ul" || tag === "ol") {
        return [...node.children]
          .filter((child) => child.tagName === "LI")
          .map((item, index) => {
            const marker = tag === "ol" ? `${index + 1}.` : "-";
            return `${marker} ${renderInline(item).trim()}`;
          })
          .join("\n");
      }

      // 일반 컨테이너는 자식 블록을 순서대로 변환
      if (tag === "div" || tag === "section") {
        return [...node.childNodes]
          .map(renderBlock)
          .filter(Boolean)
          .join("\n\n");
      }

      return renderInline(node);
    }

    return [...root.childNodes]
      .map(renderBlock)
      .filter(Boolean)
      .join("\n\n")
      .trim();
  }

  function scanMessages() {
    for (const element of getMessages()) {
      const role = element.getAttribute(
        "data-message-author-role"
      );

      const messageId =
        element.getAttribute("data-message-id") ??
        element.closest("[data-turn-id]")
          ?.getAttribute("data-turn-id") ??
        null;

      const contentElement =
        role === "assistant"
          ? element.querySelector(".markdown") ??
            element.querySelector(".prose") ??
            element
          : element.querySelector(".whitespace-pre-wrap") ??
            element;

      const content =
        role === "assistant"
          ? extractAssistantMarkdown(contentElement)
          : contentElement.innerText.trim();

      if (!content) continue;

      // message_id가 없을 때는 임시로 본문을 사용한다.
      const key = messageId ?? `${role}:${content}`;

      // 이미 수집한 메시지는 다시 추가하지 않는다.
      if (!collected.has(key)) {
        collected.set(key, {
          role,
          message_id: messageId,
          content,
        });
      }
    }
  }

  let reachedTop = false;
  let reachedBottom = false;

  try {
    scroller.style.scrollBehavior = "auto";

    // 1. 현재 위치에서 맨 위로 이동
    for (let i = 0; i < 300; i++) {
      if (scroller.scrollTop <= 2) {
        reachedTop = true;
        break;
      }

      const before = scroller.scrollTop;

      scroller.scrollTop = Math.max(
        0,
        before - step
      );

      await sleep(300);

      if (Math.abs(scroller.scrollTop - before) < 1) {
        break;
      }
    }

    reachedTop ||= scroller.scrollTop <= 2;

    // 맨 위 메시지가 렌더링될 시간을 준다.
    await sleep(500);

    // 2. 맨 위에서부터 아래로 수집
    scanMessages();

    for (let i = 0; i < 300; i++) {
      const maxScroll = Math.max(
        0,
        scroller.scrollHeight - scroller.clientHeight
      );

      if (scroller.scrollTop >= maxScroll - 2) {
        // 마지막에 추가 렌더링되는 내용 확인
        await sleep(400);
        scanMessages();

        const newMax = Math.max(
          0,
          scroller.scrollHeight - scroller.clientHeight
        );

        if (scroller.scrollTop >= newMax - 2) {
          reachedBottom = true;
          break;
        }
      }

      scroller.scrollTop = Math.min(
        maxScroll,
        scroller.scrollTop + step
      );

      await sleep(300);

      scanMessages();
    }
  } finally {
    // 성공하거나 오류가 발생해도 원래 위치 복원
    scroller.scrollTop = originalTop;
    scroller.style.scrollBehavior = originalBehavior;
  }

  const messages = [...collected.values()];

  const conversationMatch =
    location.pathname.match(/\/c\/([^/]+)/);

  return {
    ok: true,
    provider: "chatgpt",
    external_id: conversationMatch?.[1] ?? null,
    source_url: location.href,
    title: document.title,
    messages,
    diagnostics: {
      message_count: messages.length,
      reached_top: reachedTop,
      reached_bottom: reachedBottom,
      first_message_role: messages[0]?.role ?? null,
    },
  };
}
