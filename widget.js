(function() {
  var APP_URL = "https://annizon-chatbot-vfphwhkad7y4tf3qwrcc8m.streamlit.app/?embedded=true";
  var css = "#anni-bubble{position:fixed;bottom:20px;right:20px;width:60px;height:60px;border-radius:50%;background:#ffffff;color:#fff;font-size:28px;border:none;cursor:pointer;z-index:9999;box-shadow:0 4px 12px rgba(0,0,0,.3)}#anni-panel{position:fixed;bottom:95px;right:20px;width:380px;max-width:calc(100vw - 40px);height:600px;max-height:70vh;border-radius:16px;overflow:hidden;z-index:9999;box-shadow:0 8px 30px rgba(0,0,0,.35);display:none;background:#0e1117}#anni-panel iframe{width:100%;height:100%;border:none}";
  var style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);
  var panel = document.createElement("div");
  panel.id = "anni-panel";
  var iframe = document.createElement("iframe");
  iframe.src = APP_URL;
  iframe.title = "Annizon chat";
  panel.appendChild(iframe);
  document.body.appendChild(panel);
  var bubble = document.createElement("button");
  bubble.id = "anni-bubble";
  bubble.textContent = "💬";
  bubble.setAttribute("aria-label", "Chat with us");
  bubble.onclick = function() {
    panel.style.display = (panel.style.display === "block") ? "none" : "block";
  };
  document.body.appendChild(bubble);
})();
