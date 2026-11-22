-- 夜莺打字统计（作者自用，2026-11-22）：记下自己实际怎么打字，用来对照码表的词序和词频。
-- 只存累计次数，不存整句原文。用户目录 yeying_typing_stats.txt，每行一条，Tab 分隔：
--   c  码  上屏文字  第几选(1起)  次数     —— 每次从候选上屏
--   r  码  次数                           —— 按回车把编码本身上屏（或码没有候选时直接上屏）
--   e  码  次数                           —— 打了码又按 Esc 放弃（想打的没有、码打错）
--   s  片段1|片段2[|片段3]  次数           —— 连着上屏的两段、三段汉字（世界|观、世|界|观），分析时拼起来找漏掉的词
-- 两次上屏之间隔了标点、非汉字、或超过 GAP 秒，就不算连着打。
-- 暂停记录：在用户目录放一个空文件 yeying_typing_stats.off（删掉就恢复）。
-- 挂法：方案补丁 engine/processors/@before 0: lua_processor@*yeying_typing_log
local M = {}
local FILE, OFF = 'yeying_typing_stats.txt', 'yeying_typing_stats.off'
local GAP, FLUSH_N, FLUSH_SEC = 8, 20, 120
local pending, npending, last_flush = {}, 0, os.time()
local chain, last_time, break_after = {}, 0, false
local dir_cache

local function dir()
  if not dir_cache then
    dir_cache = rime_api and rime_api.get_user_data_dir and rime_api.get_user_data_dir() or '.'
  end
  return dir_cache
end

local function off()
  local f = io.open(dir() .. '/' .. OFF, 'r')
  if f then f:close(); return true end
  return false
end

local function add(key)
  pending[key] = (pending[key] or 0) + 1
  npending = npending + 1
end

-- 写盘：读出文件里已有的累计数，加上内存里新增的，整份重写（几个会话同时写也不会互相覆盖掉计数）
local function flush()
  if npending == 0 then return end
  local path = dir() .. '/' .. FILE
  local total, order = {}, {}
  local f = io.open(path, 'r')
  if f then
    for line in f:lines() do
      local k, n = line:match('^(.-)\t(%d+)$')
      if k then
        if not total[k] then order[#order + 1] = k end
        total[k] = (total[k] or 0) + tonumber(n)
      end
    end
    f:close()
  end
  for k, n in pairs(pending) do
    if not total[k] then order[#order + 1] = k end
    total[k] = (total[k] or 0) + n
  end
  local w = io.open(path .. '.tmp', 'w')
  if not w then return end
  for _, k in ipairs(order) do w:write(k, '\t', total[k], '\n') end
  w:close()
  if os.rename(path .. '.tmp', path) then pending, npending, last_flush = {}, 0, os.time() end
end

-- 全是汉字（含〇）才算能拼词的片段
local function all_hanzi(s)
  if s == '' then return false end
  for _, cp in utf8.codes(s) do
    local han = (cp >= 0x3400 and cp <= 0x9FFF) or (cp >= 0xF900 and cp <= 0xFAFF) or (cp >= 0x20000 and cp <= 0x3FFFF) or cp == 0x3007
    if not han then return false end
  end
  return true
end

local function piece(text)
  local now = os.time()
  if not all_hanzi(text) then chain = {}; last_time = now; return end
  if now - last_time > GAP then chain = {} end
  last_time = now
  chain[#chain + 1] = text
  if #chain > 3 then table.remove(chain, 1) end
  if #chain >= 2 then add('s\t' .. chain[#chain - 1] .. '|' .. chain[#chain]) end
  if #chain >= 3 then add('s\t' .. table.concat(chain, '|')) end
end

local function on_commit(ctx)
  if off() then chain = {}; return end
  local input = ctx.input or ''
  local ok = pcall(function()
    for _, seg in ipairs(ctx.composition:toSegmentation():get_segments()) do
      local code = input:sub(seg.start + 1, seg._end)
      local cand = seg:get_selected_candidate()
      if seg:has_tag('punct') or not code:match('^[a-z]+$') then
        chain = {}
      elseif cand then
        add('c\t' .. code .. '\t' .. cand.text .. '\t' .. (seg.selected_index + 1))
        piece(cand.text)
      else
        add('r\t' .. code); chain = {}
      end
    end
  end)
  if not ok then chain = {} end
  if break_after then chain = {}; break_after = false end
  if npending >= FLUSH_N or os.time() - last_flush >= FLUSH_SEC then pcall(flush) end
end

function M.init(env)
  env.yy_log = env.engine.context.commit_notifier:connect(on_commit)
end

function M.fini(env)
  if env.yy_log then env.yy_log:disconnect() end
  pcall(flush)
end

-- 看按键断开“连着打”：标点、回车、方向键、Cmd 组合键（粘贴等）都算断开。
-- 正在输入时按标点，当前的字会先顶上屏，所以只做标记，等这次上屏记完再断开。
local SELECT = { [0x20] = true, [0x3b] = true, [0x27] = true }   -- 空格、分号、引号（选字）
function M.func(key, env)
  if key:release() then return 2 end
  local kc = key.keycode
  if kc >= 0xffe1 and kc <= 0xffee then return 2 end             -- 单按修饰键
  local letter = kc >= 0x61 and kc <= 0x7a and not key:ctrl() and not key:super() and not key:alt()
  if letter then
    if break_after then chain = {}; break_after = false end
    return 2
  end
  local ctx = env.engine.context
  if ctx:is_composing() then
    local input = ctx.input or ''
    if input:match('^[a-z]+$') and not key:ctrl() and not key:super() and not off() then
      if kc == 0xff1b then add('e\t' .. input)                   -- Esc 放弃了这个码
      elseif kc == 0xff0d or kc == 0xff8d then add('r\t' .. input); break_after = true end   -- 回车上屏编码本身
    end
    local digit = kc >= 0x31 and kc <= 0x39
    if not (SELECT[kc] or digit) and kc >= 0x21 and kc <= 0x7e then break_after = true end
  else
    chain = {}
  end
  return 2
end

return M
