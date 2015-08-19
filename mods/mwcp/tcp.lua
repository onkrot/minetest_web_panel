local function warning(msg)
	print("[WARNING] " .. msg)
end

local process_frompanel = nil
local lib           = nil
local ltn12         = nil
local sync_timeout  = nil
local server_id     = nil
local auth_key      = nil
local webpanel_host = nil
local socket        = nil
local function init(iprocess_frompanel, data)
	process_frompanel = iprocess_frompanel
	sync_timeout  = data.sync_timeout
	server_id     = data.server_id
	auth_key      = data.auth_key
	webpanel_host = data.webpanel_host

	-- Include modules
	local ie = _G
	if minetest.request_insecure_environment then
		ie = minetest.request_insecure_environment()
		if not ie then
			error("Insecure environment required!")
		end
	end

	lib   = ie.require("socket")
	ltn12 = ie.require("ltn12")
  local host, port = split(webpanel_host,":")
	socket = lib.connect(host, port)
  socket:settimeout(sync_timeout)
	local setup = {type = "auth", server_id = server_id, auth_key = auth_key}
	local json = minetest.write_json(setup)
	socket:send(json)
end

local function validate_response(resp)
	if resp == "auth" then
		warning("Authentication error when requesting commands from webpanel")
		return false
	end

	if resp == "offline" then
		warning("The webpanel reports that this server should be offline!")
		return false
	end

	return true
end

local function validate_response_json(resp)

	if not validate_response(resp) then
		return false
	end

	if string.find(resp, "%[", 1) == nil then
		warning("The webpanel gave an invalid response!")
		print(dump(resp))
		return false
	end

	return true
end

local function sync()
    local resp = socket:receive()
		if validate_response_json(resp) then
    	process_frompanel(minetest.parse_json(resp))
		end
end

local function send(data)
		local json = minetest.write_json(data)
		socket:send(json)
end

return {
	init = init,
	sync = sync,
	send = send
}
