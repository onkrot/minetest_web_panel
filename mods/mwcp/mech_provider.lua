local function get_provider(method)
  if method == "http" then
    local http = dofile(minetest.get_modpath("mwcp") .. "/http.lua")
    return {
      init = http.init,
      sync = http.sync,
      send = http.send
    }
  end
end

return {
  get_provider = get_provider
}
