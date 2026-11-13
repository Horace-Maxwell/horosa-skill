// The real shell pulls in a UI kit. The harvester stubs every bare package except react; named imports must still resolve.
import { Select } from 'antd';

export const XQSelect = Select;
XQSelect.Option = Select.Option;
