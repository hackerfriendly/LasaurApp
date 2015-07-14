
var hardware_ready_state = false;
var lasaurapp_version_reported = false;
var progress_not_yet_done_flag = false;


(function($){
  $.fn.uxmessage = function(kind, text, max_length) {
    if (max_length == null) {
      max_length = 100;
    }

    if (text.length > max_length) {
      text = text.slice(0,max_length) + '\n...'
    }

    text = text.replace(/\n/g,'<br>')

    if (kind == 'notice') {
      $('#log_content').prepend('<div class="log_item log_notice well" style="display:none">' + text + '</div>');
      $('#log_content').children('div').first().show('blind');
      if ($("#log_content").is(':hidden')) {
        $().toastmessage('showNoticeToast', text);
      }
    } else if (kind == 'success') {
      $('#log_content').prepend('<div class="log_item log_success well" style="display:none">' + text + '</div>');
      $('#log_content').children('div').first().show('blind');
      if ($("#log_content").is(':hidden')) {
        $().toastmessage('showSuccessToast', text);
      }
    } else if (kind == 'warning') {
      $('#log_content').prepend('<div class="log_item log_warning well" style="display:none">' + text + '</div>');
      $('#log_content').children('div').first().show('blind');
      if ($("#log_content").is(':hidden')) {
        $().toastmessage('showWarningToast', text);
      }
    } else if (kind == 'error') {
      $('#log_content').prepend('<div class="log_item log_error well" style="display:none">' + text + '</div>');
      $('#log_content').children('div').first().show('blind');
      if ($("#log_content").is(':hidden')) {
        $().toastmessage('showErrorToast', text);
      }
    }

    while ($('#log_content').children('div').length > 200) {
      $('#log_content').children('div').last().remove();
    }

  };
})(jQuery);


function send_gcode(gcode, success_msg, progress, post_to) {
  if (typeof gcode === "string" && gcode != '') {
    if (! post_to) {
      post_to = "/gcode";
    }
    // $().uxmessage('notice', gcode, Infinity);
    $.ajax({
      type: "POST",
      url: post_to,
      data: {'job_data':gcode},
      // dataType: "json",
      success: function (data) {
        if (data == "__ok__") {
          $().uxmessage('success', success_msg);
          if (progress = true) {
            // show progress bar, register live updates
            if ($("#progressbar").children().first().width() == 0) {
              $("#progressbar").children().first().width('5%');
              $("#progressbar").show();
              progress_not_yet_done_flag = true;
              setTimeout(update_progress, 2000);
            }
          }
        } else {
          $().uxmessage('error', "Backend error: " + data);
        }
      },
      error: function (data) {
        $().uxmessage('error', "Timeout. LaserRaptor server down?");
      },
      complete: function (data) {
        // future use
      }
    });
  } else {
    $().uxmessage('error', "No gcode.");
  }
}


function update_progress() {
  $.get('/queue_pct_done', function(data) {
    if (data.length > 0) {
      var pct = parseInt(data);
      $("#progressbar").children().first().width(pct+'%');
      setTimeout(update_progress, 2000);
    } else {
      if (progress_not_yet_done_flag) {
        $("#progressbar").children().first().width('100%');
        $().uxmessage('notice', "Done.");
        progress_not_yet_done_flag = false;
        setTimeout(update_progress, 2000);
      } else {
        $('#progressbar').hide();
        $("#progressbar").children().first().width(0);
      }
    }
  });
}


function open_bigcanvas(scale, deselectedColors) {
  var w = scale * app_settings.canvas_dimensions[0];
  var h = scale * app_settings.canvas_dimensions[1];
  $('#container').before('<a id="close_big_canvas" href="#"><canvas id="big_canvas" width="'+w+'px" height="'+h+'px" style="border:1px dashed #aaaaaa;"></canvas></a>');
  var mid = $('body').innerWidth()/2.0-30;
  $('#close_big_canvas').click(function(e){
    close_bigcanvas();
    return false;
  });
  $("html").on('keypress.closecanvas', function (e) {
    if ((e.which && e.which == 13) || (e.keyCode && e.keyCode == 13) ||
        (e.which && e.which == 27) || (e.keyCode && e.keyCode == 27)) {
      // on enter or escape
      close_bigcanvas();
      return false;
    } else {
      return true;
    }
  });
  // $('#big_canvas').focus();
  $('#container').hide();
  var bigcanvas = new Canvas('#big_canvas');
  // DataHandler.draw(bigcanvas, 4*app_settings.to_canvas_scale, getDeselectedColors());
  if (deselectedColors === undefined) {
    DataHandler.draw(bigcanvas, scale*app_settings.to_canvas_scale);
  } else {
    DataHandler.draw(bigcanvas, scale*app_settings.to_canvas_scale, deselectedColors);
  }
}


function close_bigcanvas() {
  $('#big_canvas').remove();
  $('#close_big_canvas').remove();
  $('html').off('keypress.closecanvas');
  delete bigcanvas;
  $('#container').show();
}


function generate_download(filename, filedata) {
  $.ajax({
    type: "POST",
    url: "/stash_download",
    data: {'filedata': filedata},
    success: function (data) {
      window.open("/download/" + data + "/" + filename, '_blank');
    },
    error: function (data) {
      $().uxmessage('error', "Timeout. LaserRaptor server down?");
    },
    complete: function (data) {
      // future use
    }
  });
}


///////////////////////////////////////////////////////////////////////////////
///////////////////////////////////////////////////////////////////////////////



$(document).ready(function(){

  $().uxmessage('notice', "Frontend started.");

  $('#feedrate_field').val(app_settings.max_seek_speed);

  $('#tab_logs_button').click(function(){
    $('#log_content').show()
    $('#tab_logs div.alert').show()
  })


  //////// serial connect and pause button ////////
  var connect_btn_state = false;
  var connect_btn_in_hover = false;
  var pause_btn_state = false;

  function connect_btn_set_state(is_connected) {
    if (is_connected) {
      connect_btn_state = true
      if (!connect_btn_in_hover) {
        $("#connect_btn").html("Connected");
      }
      $("#connect_btn").removeClass("btn-danger");
      $("#connect_btn").removeClass("btn-warning");
      $("#connect_btn").addClass("btn-success");
    } else {
      connect_btn_state = false
      if (!connect_btn_in_hover) {
        $("#connect_btn").html("Disconnected");
      }
      $("#connect_btn").removeClass("btn-danger");
      $("#connect_btn").removeClass("btn-success");
      $("#connect_btn").addClass("btn-warning");
    }
  }

  // get hardware status
  function poll_hardware_status() {
    $.getJSON('/status', function(data) {
      // serial connected
      if (data.serial_connected) {
        connect_btn_set_state(true);
      } else {
        connect_btn_set_state(false);
      }

      // ready state
      if (data.ready) {
        hardware_ready_state = true;
        $("#connect_btn").html("Ready");
      } else {
        if (data.serial_connected) {
          $("#connect_btn").html("Busy");
        }
        hardware_ready_state = false;
      }

      // door, chiller, power, limit, buffer
      if (data.serial_connected) {
        if (data.door_open) {
          $('#door_status_btn').removeClass('btn-success')
          $('#door_status_btn').addClass('btn-warning')
          // $().uxmessage('warning', "Door is open!");
        } else {
          $('#door_status_btn').removeClass('btn-warning')
          $('#door_status_btn').addClass('btn-success')
        }
        if (data.chiller_off) {
          $('#chiller_status_btn').removeClass('btn-success')
          $('#chiller_status_btn').addClass('btn-warning')
          // $().uxmessage('warning', "Chiller is off!");
        } else {
          $('#chiller_status_btn').removeClass('btn-warning')
          $('#chiller_status_btn').addClass('btn-success')
        }
        if (data.power_off) {
          $().uxmessage('error', "Power is off!");
          $().uxmessage('notice', "Turn on LaserRaptor power then run homing cycle to reset.");
        }
        if (data.limit_hit) {
          $().uxmessage('error', "Limit hit!");
          $().uxmessage('notice', "Run homing cycle to reset stop mode.");
        }
        if (data.buffer_overflow) {
          $().uxmessage('error', "Rx Buffer Overflow!");
          $().uxmessage('notice', "Please report this to the author of this software.");
        }
        if (data.transmission_error) {
          $().uxmessage('error', "Transmission Error!");
          $().uxmessage('notice', "If this happens a lot tell the author of this software.");
        }
        if (data.x && data.y) {
          // only update if not manually entering at the same time
          if (!$('#x_location_field').is(":focus") &&
              !$('#y_location_field').is(":focus") &&
              !$('#location_set_btn').is(":focus") &&
              !$('#origin_set_btn').is(":focus"))
          {
            var x = parseFloat(data.x).toFixed(2) - app_settings.table_offset[0];
            $('#x_location_field').val(x.toFixed(2));
            $('#x_location_field').animate({
              opacity: 0.5
            }, 100, function() {
              $('#x_location_field').animate({
                opacity: 1.0
              }, 600, function() {});
            });
            var y = parseFloat(data.y).toFixed(2) - app_settings.table_offset[1];
            $('#y_location_field').val(y.toFixed(2));
            $('#y_location_field').animate({
              opacity: 0.5
            }, 100, function() {
              $('#y_location_field').animate({
                opacity: 1.0
              }, 600, function() {});
            });
          }
        }
      }
      if (data.lasaurapp_version && !lasaurapp_version_reported) {
        $().uxmessage('notice', "LaserRaptor v" + data.lasaurapp_version);
        $('#lasaurapp_version').html(data.lasaurapp_version);
        lasaurapp_version_reported = true;
      }
      // schedule next hardware poll
      setTimeout(function() {poll_hardware_status()}, 4000);
    }).error(function() {
      // lost connection to server
      connect_btn_set_state(false);
      // schedule next hardware poll
      setTimeout(function() {poll_hardware_status()}, 8000);
    });
  }
  // kick off hardware polling
  poll_hardware_status();

  connect_btn_width = $("#connect_btn").innerWidth();
  $("#connect_btn").width(connect_btn_width);
  $("#connect_btn").click(function(e){
    if (connect_btn_state == true) {
      $.get('/serial/0', function(data) {
        if (data != "") {
          connect_btn_set_state(false);
        } else {
          // was already disconnected
          connect_btn_set_state(false);
        }
        $("#connect_btn").html("Disconnected");
      });
    } else {
      $("#connect_btn").html('Connecting...');
      $.get('/serial/1', function(data) {
        if (data != "") {
          connect_btn_set_state(true);
          $("#connect_btn").html("Connected");
        } else {
          // failed to connect
          connect_btn_set_state(false);
          $("#connect_btn").removeClass("btn-warning");
          $("#connect_btn").addClass("btn-danger");
        }
      });
    }
    e.preventDefault();
  });
  $("#connect_btn").hover(
    function () {
      connect_btn_in_hover = true;
      if (connect_btn_state) {
        $(this).html("Disconnect");
      } else {
        $(this).html("Connect");
      }
      $(this).width(connect_btn_width);
    },
    function () {
      connect_btn_in_hover = false;
      if (connect_btn_state) {
        $(this).html("Connected");
      } else {
        $(this).html("Disconnected");
      }
      $(this).width(connect_btn_width);
    }
  );

  $("#pause_btn").tooltip({placement:'bottom', delay: {show:500, hide:100}});
  $("#pause_btn").click(function(e){
    if (pause_btn_state == true) {  // unpause
      send_gcode("M24", "Resuming...", false);
      pause_btn_state = false;
      $("#pause_btn").removeClass('btn-primary');
      $("#pause_btn").removeClass('btn-warning');
      $("#pause_btn").html('<i class="icon-pause"></i>');
    } else {  // pause
      $("#pause_btn").addClass('btn-warning');
      send_gcode("M25", "Pausing...", false);
      pause_btn_state = true;
      $("#pause_btn").removeClass("btn-warning");
      $("#pause_btn").addClass('btn-primary');
      $("#pause_btn").html('<i class="icon-play"></i>');
    };
    e.preventDefault();
  });

  $("#cancel_btn").tooltip({placement:'bottom', delay: {show:500, hide:100}});
  $("#cancel_btn").click(function(e){
    var gcode = 'M26\nM112'  // enter stop state
    send_gcode(gcode, "Stopping ...", false);
    var delayedresume = setTimeout(function() {
      var gcode = 'M999' // reset
      send_gcode(gcode, "Ready.", false);
    }, 1000);
    e.preventDefault();
  });

  $("#homing_cycle").tooltip({placement:'bottom', delay: {show:500, hide:100}});
  $("#homing_cycle").click(function(e){
    send_gcode('M26\nM112', "Stopping ...", false);
    var delayedresume = setTimeout(function() {
      send_gcode('M999', "Starting ...", false);
      if(offsetEnabled) {
        reset_offset();
      }
      else {
        send_gcode('G28', "Going home ...", false);
      }
    }, 1000);

    e.preventDefault();

  });

  $("#go_to_origin").tooltip({placement:'bottom', delay: {show:500, hide:100}});
  $("#go_to_origin").click(function(e){
    var gcode;
    if(e.shiftKey) {
      // also reset offset
      reset_offset();
    }
    gcode = 'G90\nG0X0Y0F'+app_settings.max_seek_speed+'\n'
    // $().uxmessage('notice', gcode);
    send_gcode(gcode, "Going to origin ...", false);
    e.preventDefault();
  });

  /// tab shortcut keys /////////////////////////
  $(document).on('keypress', null, 'p', function(e){
    $('#pause_btn').trigger('click');
    return false;
  });

  $(document).on('keypress', null, '0', function(e){
    $('#go_to_origin').trigger('click');
    return false;
  });

  var cancel_modal_active = false;
  $(document).on('keyup', null, 'esc', function(e){
    if (cancel_modal_active === true) {
      $('#cancel_modal').modal('hide');
      cancel_modal_active = false;
    } else {
      $('#cancel_modal').modal('show');
      $('#really_cancel_btn').focus();
      cancel_modal_active = true;
    }
    return false;
  });

  $('#really_cancel_btn').click(function(e){
    $('#cancel_btn').trigger('click');
    $('#cancel_modal').modal('hide');
    cancel_modal_active = false;
  });



  /// tab shortcut keys /////////////////////////

  $(document).on('keypress', null, 'j', function(e){
    $('#tab_jobs_button').trigger('click');
    return false;
  });

  $(document).on('keypress', null, 'i', function(e){
    $('#tab_import_button').trigger('click');
    return false;
  });

  $(document).on('keypress', null, 'm', function(e){
    $('#tab_mover_button').trigger('click');
    return false;
  });

  $(document).on('keypress', null, 'l', function(e){
    $('#tab_logs_button').trigger('click');
    return false;
  });

});  // ready
