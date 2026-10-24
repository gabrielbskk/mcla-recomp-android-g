# A Termux host may need a wrapper to load the code generator's host libraries.
# Keep its environment separate from both the compiler and Android runtime.
set(REXGLUE_CODEGEN_EXECUTABLE "" CACHE FILEPATH "Host-native ReXGlue executable or wrapper")
set(MCLA_CODEGEN_DEPENDS "")
if(REXGLUE_CODEGEN_EXECUTABLE)
    get_filename_component(MCLA_CODEGEN_COMMAND "${REXGLUE_CODEGEN_EXECUTABLE}"
                           ABSOLUTE BASE_DIR "${CMAKE_SOURCE_DIR}")
    if(NOT EXISTS "${MCLA_CODEGEN_COMMAND}" OR IS_DIRECTORY "${MCLA_CODEGEN_COMMAND}")
        message(FATAL_ERROR "Host codegen executable not found: ${MCLA_CODEGEN_COMMAND}")
    endif()
    set(MCLA_CODEGEN_DEPENDS "${MCLA_CODEGEN_COMMAND}")
else()
    set(MCLA_CODEGEN_COMMAND "$<TARGET_FILE:rex::rexglue>")
endif()

# Codegen rewrites generated/rexglue.cmake. Adapt a build-directory copy at
# configure time instead of editing that generated source or the cached SDK.
function(mcla_prepare_codegen_cmake source destination)
    file(READ "${source}" boilerplate)
    set(original [=[COMMAND $<TARGET_FILE:rex::rexglue> codegen]=])
    string(FIND "${boilerplate}" "${original}" position)
    if(position EQUAL -1)
        message(FATAL_ERROR "Unrecognized ReXGlue codegen rule in ${source}; review the SDK template")
    endif()
    set(replacement [=[DEPENDS ${MCLA_CODEGEN_DEPENDS}
    COMMAND "${MCLA_CODEGEN_COMMAND}" codegen]=])
    string(REPLACE "${original}" "${replacement}" patched "${boilerplate}")
    file(CONFIGURE OUTPUT "${destination}" CONTENT "${patched}" @ONLY)
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${source}")
endfunction()
