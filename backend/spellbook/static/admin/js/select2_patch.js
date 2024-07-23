// https://github.com/select2/select2/issues/3335#issuecomment-1218072422
var AllowClear = django.jQuery.fn.select2.amd.require('select2/selection/allowClear');
var _handleKeyboardClearOriginal = AllowClear.prototype._handleKeyboardClear;

AllowClear.prototype._handleKeyboardClear = function(_, evt, container) {
  if (this.$element.prop('multiple')) {
    return;
  }

  _handleKeyboardClearOriginal.call(this, _, evt, container);
};
